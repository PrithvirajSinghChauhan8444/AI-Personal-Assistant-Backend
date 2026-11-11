package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"sync"
	"time"
)

// ASTField represents a field or parameter discovered via AST analysis.
type ASTField struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Tag         string `json:"tag,omitempty"`
	JSONName    string `json:"json_name,omitempty"`
	Doc         string `json:"doc,omitempty"`
	IsExported  bool   `json:"is_exported"`
	IsRequired  bool   `json:"is_required"`
}

// ASTMethod represents an exported receiver method or function discovered via AST.
type ASTMethod struct {
	ID                  string     `json:"id"`
	Name                string     `json:"name"`
	Package             string     `json:"package"`
	Receiver            string     `json:"receiver,omitempty"` // e.g. "*Gateway"
	ReceiverRaw         string     `json:"receiver_raw,omitempty"` // e.g. "Gateway"
	Signature           string     `json:"signature"`
	Doc                 string     `json:"doc"`
	Params              []ASTField `json:"params"`
	Returns             []string   `json:"returns"`
	FilePath            string     `json:"file_path"`
	LineNumber          int        `json:"line_number"`
	IsCallable          bool       `json:"is_callable"`
	HasRegisteredRunner bool       `json:"has_registered_runner"`
	RegisteredModuleID  string     `json:"registered_module_id,omitempty"`
}

// ASTType represents a struct, interface, or type definition discovered in source.
type ASTType struct {
	Name        string     `json:"name"`
	Package     string     `json:"package"`
	Kind        string     `json:"kind"` // "struct", "interface", "type", "alias"
	Doc         string     `json:"doc"`
	Fields      []ASTField `json:"fields,omitempty"`
	Methods     []string   `json:"methods,omitempty"`
	FilePath    string     `json:"file_path"`
	LineNumber  int        `json:"line_number"`
	IsExported  bool       `json:"is_exported"`
}

// ASTPackage represents a scanned Go package.
type ASTPackage struct {
	Name       string      `json:"name"`
	RelPath    string      `json:"rel_path"`
	Doc        string      `json:"doc"`
	Files      []string    `json:"files"`
	Types      []ASTType   `json:"types"`
	Methods    []ASTMethod `json:"methods"`
	Functions  []ASTMethod `json:"functions"`
}

// ASTScanSummary provides high-level discovery metrics.
type ASTScanSummary struct {
	PackageCount    int `json:"package_count"`
	FileCount       int `json:"file_count"`
	TypeCount       int `json:"type_count"`
	MethodCount     int `json:"method_count"`
	FunctionCount   int `json:"function_count"`
	CallableCount   int `json:"callable_count"`
	IntegratedCount int `json:"integrated_count"`
}

// ASTScanResult represents the complete scan outcome.
type ASTScanResult struct {
	ScannedAt   time.Time      `json:"scanned_at"`
	RootDir     string         `json:"root_dir"`
	Packages    []ASTPackage   `json:"packages"`
	AllMethods  []ASTMethod    `json:"all_methods"`
	AllTypes    []ASTType      `json:"all_types"`
	Summary     ASTScanSummary `json:"summary"`
}

// ASTScanner parses Go source files using go/parser and go/ast.
type ASTScanner struct {
	mu         sync.RWMutex
	rootDir    string
	lastResult *ASTScanResult
	registry   *Registry
}

// NewASTScanner creates a scanner configured for the specified root source directory.
func NewASTScanner(rootDir string, reg *Registry) *ASTScanner {
	return &ASTScanner{
		rootDir:  rootDir,
		registry: reg,
	}
}

// Scan parses all .go files in rootDir (ignoring vendor, test files, and dot directories).
func (s *ASTScanner) Scan() (*ASTScanResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	fset := token.NewFileSet()
	packagesMap := make(map[string]*ASTPackage)
	var allFiles []string

	// Walk directory to find all Go files
	err := filepath.Walk(s.rootDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			name := info.Name()
			if strings.HasPrefix(name, ".") || name == "vendor" || name == "testdata" || name == "node_modules" {
				return filepath.SkipDir
			}
			return nil
		}

		if strings.HasSuffix(path, ".go") && !strings.HasSuffix(path, "_test.go") {
			allFiles = append(allFiles, path)
		}
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("error walking source directory: %w", err)
	}

	// Parse AST for each file
	for _, filePath := range allFiles {
		node, err := parser.ParseFile(fset, filePath, nil, parser.ParseComments)
		if err != nil {
			continue // skip unparseable files
		}

		pkgName := node.Name.Name
		dirPath := filepath.Dir(filePath)
		relDir, _ := filepath.Rel(s.rootDir, dirPath)
		if relDir == "" || relDir == "." {
			relDir = pkgName
		}

		pkgKey := dirPath
		pkg, exists := packagesMap[pkgKey]
		if !exists {
			pkg = &ASTPackage{
				Name:    pkgName,
				RelPath: filepath.ToSlash(relDir),
				Files:   make([]string, 0),
			}
			if node.Doc != nil {
				pkg.Doc = strings.TrimSpace(node.Doc.Text())
			}
			packagesMap[pkgKey] = pkg
		}

		relFile, _ := filepath.Rel(".", filePath)
		pkg.Files = append(pkg.Files, filepath.ToSlash(relFile))

		// Inspect Declarations
		for _, decl := range node.Decls {
			switch d := decl.(type) {
			case *ast.GenDecl:
				s.inspectGenDecl(fset, d, filePath, pkg)
			case *ast.FuncDecl:
				s.inspectFuncDecl(fset, d, filePath, pkg)
			}
		}
	}

	// Collect into result
	result := &ASTScanResult{
		ScannedAt:  time.Now(),
		RootDir:    s.rootDir,
		Packages:   make([]ASTPackage, 0, len(packagesMap)),
		AllMethods: make([]ASTMethod, 0),
		AllTypes:   make([]ASTType, 0),
	}

	// Map registered modules for fast matching
	registeredMap := make(map[string]string)
	if s.registry != nil {
		for _, m := range s.registry.List() {
			registeredMap[strings.ToLower(m.ID)] = m.ID
			registeredMap[strings.ToLower(m.Name)] = m.ID
		}
	}

	for _, pkg := range packagesMap {
		// Sort items
		sort.Slice(pkg.Types, func(i, j int) bool { return pkg.Types[i].Name < pkg.Types[j].Name })
		sort.Slice(pkg.Methods, func(i, j int) bool { return pkg.Methods[i].Name < pkg.Methods[j].Name })
		sort.Slice(pkg.Functions, func(i, j int) bool { return pkg.Functions[i].Name < pkg.Functions[j].Name })

		// Enhance methods with integration status
		for idx := range pkg.Methods {
			m := &pkg.Methods[idx]
			s.matchRegisteredRunner(m, registeredMap)
			result.AllMethods = append(result.AllMethods, *m)
		}
		for idx := range pkg.Functions {
			f := &pkg.Functions[idx]
			s.matchRegisteredRunner(f, registeredMap)
			result.AllMethods = append(result.AllMethods, *f)
		}

		result.AllTypes = append(result.AllTypes, pkg.Types...)
		result.Packages = append(result.Packages, *pkg)
	}

	// Sort packages by path
	sort.Slice(result.Packages, func(i, j int) bool {
		return result.Packages[i].RelPath < result.Packages[j].RelPath
	})
	sort.Slice(result.AllMethods, func(i, j int) bool {
		return result.AllMethods[i].Signature < result.AllMethods[j].Signature
	})

	// Generate summary
	result.Summary.PackageCount = len(result.Packages)
	result.Summary.FileCount = len(allFiles)
	result.Summary.TypeCount = len(result.AllTypes)
	for _, p := range result.Packages {
		result.Summary.MethodCount += len(p.Methods)
		result.Summary.FunctionCount += len(p.Functions)
	}
	for _, m := range result.AllMethods {
		if m.IsCallable {
			result.Summary.CallableCount++
		}
		if m.HasRegisteredRunner {
			result.Summary.IntegratedCount++
		}
	}

	s.lastResult = result
	return result, nil
}

// GetLastResult returns the cached scan result, or runs a scan if nil.
func (s *ASTScanner) GetLastResult() (*ASTScanResult, error) {
	s.mu.RLock()
	res := s.lastResult
	s.mu.RUnlock()

	if res != nil {
		return res, nil
	}
	return s.Scan()
}

func (s *ASTScanner) inspectGenDecl(fset *token.FileSet, decl *ast.GenDecl, filePath string, pkg *ASTPackage) {
	if decl.Tok != token.TYPE {
		return
	}

	docText := ""
	if decl.Doc != nil {
		docText = strings.TrimSpace(decl.Doc.Text())
	}

	for _, spec := range decl.Specs {
		typeSpec, ok := spec.(*ast.TypeSpec)
		if !ok {
			continue
		}

		typeName := typeSpec.Name.Name
		isExported := ast.IsExported(typeName)
		line := fset.Position(typeSpec.Pos()).Line

		tDoc := docText
		if typeSpec.Doc != nil {
			tDoc = strings.TrimSpace(typeSpec.Doc.Text())
		}

		astType := ASTType{
			Name:       typeName,
			Package:    pkg.Name,
			Doc:        tDoc,
			FilePath:   filepath.ToSlash(filePath),
			LineNumber: line,
			IsExported: isExported,
		}

		switch t := typeSpec.Type.(type) {
		case *ast.StructType:
			astType.Kind = "struct"
			if t.Fields != nil {
				for _, field := range t.Fields.List {
					fType := exprToString(field.Type)
					fDoc := ""
					if field.Doc != nil {
						fDoc = strings.TrimSpace(field.Doc.Text())
					} else if field.Comment != nil {
						fDoc = strings.TrimSpace(field.Comment.Text())
					}

					tagVal := ""
					jsonName := ""
					if field.Tag != nil {
						tagVal = strings.Trim(field.Tag.Value, "`")
						st := reflect.StructTag(tagVal)
						jTag := st.Get("json")
						if jTag != "" && jTag != "-" {
							jsonName = strings.Split(jTag, ",")[0]
						}
					}

					if len(field.Names) == 0 {
						// Embedded field
						astType.Fields = append(astType.Fields, ASTField{
							Name:       fType,
							Type:       fType,
							Tag:        tagVal,
							JSONName:   jsonName,
							Doc:        fDoc,
							IsExported: ast.IsExported(fType),
							IsRequired: true,
						})
					} else {
						for _, name := range field.Names {
							astType.Fields = append(astType.Fields, ASTField{
								Name:       name.Name,
								Type:       fType,
								Tag:        tagVal,
								JSONName:   jsonName,
								Doc:        fDoc,
								IsExported: ast.IsExported(name.Name),
								IsRequired: !strings.Contains(tagVal, "omitempty"),
							})
						}
					}
				}
			}

		case *ast.InterfaceType:
			astType.Kind = "interface"
			if t.Methods != nil {
				for _, m := range t.Methods.List {
					if len(m.Names) > 0 {
						astType.Methods = append(astType.Methods, m.Names[0].Name)
					}
				}
			}

		default:
			astType.Kind = "type"
		}

		pkg.Types = append(pkg.Types, astType)
	}
}

func (s *ASTScanner) inspectFuncDecl(fset *token.FileSet, decl *ast.FuncDecl, filePath string, pkg *ASTPackage) {
	name := decl.Name.Name
	if !ast.IsExported(name) {
		return // only scan exported functions and methods
	}

	docText := ""
	if decl.Doc != nil {
		docText = strings.TrimSpace(decl.Doc.Text())
	}
	line := fset.Position(decl.Pos()).Line

	var receiver string
	var receiverRaw string
	if decl.Recv != nil && len(decl.Recv.List) > 0 {
		recvType := exprToString(decl.Recv.List[0].Type)
		receiver = recvType
		receiverRaw = strings.TrimPrefix(recvType, "*")
	}

	// Parse parameters
	params := make([]ASTField, 0)
	isCallable := false
	if decl.Type.Params != nil {
		for _, field := range decl.Type.Params.List {
			fType := exprToString(field.Type)
			if fType == "context.Context" || strings.Contains(strings.ToLower(fType), "request") || strings.Contains(strings.ToLower(fType), "turn") {
				isCallable = true
			}
			if len(field.Names) == 0 {
				params = append(params, ASTField{
					Name:       "arg",
					Type:       fType,
					IsExported: true,
					IsRequired: true,
				})
			} else {
				for _, pName := range field.Names {
					params = append(params, ASTField{
						Name:       pName.Name,
						Type:       fType,
						IsExported: ast.IsExported(pName.Name),
						IsRequired: true,
					})
				}
			}
		}
	}

	// Parse return values
	returns := make([]string, 0)
	if decl.Type.Results != nil {
		for _, field := range decl.Type.Results.List {
			retType := exprToString(field.Type)
			returns = append(returns, retType)
			if strings.Contains(retType, "error") || strings.Contains(retType, "chan") {
				isCallable = true
			}
		}
	}

	// Format signature
	var sigBuilder strings.Builder
	sigBuilder.WriteString("func ")
	if receiver != "" {
		sigBuilder.WriteString("(" + receiver + ") ")
	}
	sigBuilder.WriteString(name + "(")
	paramStrs := make([]string, 0, len(params))
	for _, p := range params {
		paramStrs = append(paramStrs, fmt.Sprintf("%s %s", p.Name, p.Type))
	}
	sigBuilder.WriteString(strings.Join(paramStrs, ", "))
	sigBuilder.WriteString(")")

	if len(returns) == 1 {
		sigBuilder.WriteString(" " + returns[0])
	} else if len(returns) > 1 {
		sigBuilder.WriteString(" (" + strings.Join(returns, ", ") + ")")
	}

	id := fmt.Sprintf("%s.%s", pkg.Name, name)
	if receiverRaw != "" {
		id = fmt.Sprintf("%s.%s.%s", pkg.Name, receiverRaw, name)
	}

	method := ASTMethod{
		ID:          id,
		Name:        name,
		Package:     pkg.Name,
		Receiver:    receiver,
		ReceiverRaw: receiverRaw,
		Signature:   sigBuilder.String(),
		Doc:         docText,
		Params:      params,
		Returns:     returns,
		FilePath:    filepath.ToSlash(filePath),
		LineNumber:  line,
		IsCallable:  isCallable,
	}

	if receiver != "" {
		pkg.Methods = append(pkg.Methods, method)
	} else {
		pkg.Functions = append(pkg.Functions, method)
	}
}

func (s *ASTScanner) matchRegisteredRunner(m *ASTMethod, registeredMap map[string]string) {
	// Try matching by exact ID or pattern
	nameLower := strings.ToLower(m.Name)
	recvLower := strings.ToLower(m.ReceiverRaw)
	pkgLower := strings.ToLower(m.Package)

	// Direct check
	for key, regID := range registeredMap {
		if strings.Contains(key, nameLower) && (recvLower == "" || strings.Contains(key, recvLower) || strings.Contains(key, pkgLower)) {
			m.HasRegisteredRunner = true
			m.RegisteredModuleID = regID
			return
		}
	}
}

// exprToString converts an ast.Expr to its canonical Go type string.
func exprToString(expr ast.Expr) string {
	switch t := expr.(type) {
	case *ast.Ident:
		return t.Name
	case *ast.StarExpr:
		return "*" + exprToString(t.X)
	case *ast.SelectorExpr:
		return exprToString(t.X) + "." + t.Sel.Name
	case *ast.ArrayType:
		return "[]" + exprToString(t.Elt)
	case *ast.MapType:
		return "map[" + exprToString(t.Key) + "]" + exprToString(t.Value)
	case *ast.ChanType:
		switch t.Dir {
		case ast.RECV:
			return "<-chan " + exprToString(t.Value)
		case ast.SEND:
			return "chan<- " + exprToString(t.Value)
		default:
			return "chan " + exprToString(t.Value)
		}
	case *ast.InterfaceType:
		return "any"
	case *ast.Ellipsis:
		return "..." + exprToString(t.Elt)
	case *ast.FuncType:
		return "func(...)"
	default:
		return fmt.Sprintf("%T", expr)
	}
}

// AutoRegisterDiscoveredModules generates workbench Module entries for AST-discovered callable methods.
func (s *ASTScanner) AutoRegisterDiscoveredModules(reg *Registry) int {
	res, err := s.GetLastResult()
	if err != nil {
		return 0
	}

	added := 0
	for _, m := range res.AllMethods {
		// Only auto-register methods that are callable and don't already have a manual runner
		if !m.IsCallable || m.HasRegisteredRunner {
			continue
		}

		modID := fmt.Sprintf("ast:%s", strings.ToLower(m.ID))
		if _, exists := reg.Get(modID); exists {
			continue
		}

		// Build a FieldSchema list from parameters
		fields := make([]FieldSchema, 0, len(m.Params))
		for _, p := range m.Params {
			if p.Type == "context.Context" {
				continue
			}
			fields = append(fields, FieldSchema{
				Name:        p.Name,
				Type:        p.Type,
				Required:    p.IsRequired,
				Description: fmt.Sprintf("Parameter of type %s for %s", p.Type, m.Signature),
			})
		}

		desc := m.Doc
		if desc == "" {
			desc = fmt.Sprintf("AST-discovered method %s from %s:%d", m.Signature, m.FilePath, m.LineNumber)
		}

		mod := Module{
			ID:          modID,
			Name:        fmt.Sprintf("[AST] %s", m.ID),
			Category:    fmt.Sprintf("AST: %s", m.Package),
			Description: desc,
			Schema: ModuleSchema{
				TypeName: m.ID,
				Fields:   fields,
			},
			Presets: []Preset{
				{
					ID:          "ast-default",
					Name:        "AST Default Inspect",
					Category:    "AST Inspection",
					Description: "Default introspected payload",
					Payload:     map[string]any{"_ast_method": m.Signature, "_file": m.FilePath, "_line": m.LineNumber},
				},
			},
			Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- StreamEvent) (any, error) {
				stream <- StreamEvent{
					Index:     1,
					Timestamp: time.Now(),
					Type:      "AST_INSPECT",
					AgentName: "ASTScanner",
					Payload: map[string]any{
						"method":    m.Signature,
						"file":      m.FilePath,
						"line":      m.LineNumber,
						"doc":       m.Doc,
						"params":    m.Params,
						"returns":   m.Returns,
						"input_raw": string(inputRaw),
					},
				}
				return map[string]any{
					"status":             "AST_VERIFIED",
					"message":            fmt.Sprintf("Method %s is detected via AST at %s:%d", m.Signature, m.FilePath, m.LineNumber),
					"callable_signature": m.Signature,
					"input_received":     json.RawMessage(inputRaw),
				}, nil
			},
		}

		reg.Register(mod)
		added++
	}

	return added
}
