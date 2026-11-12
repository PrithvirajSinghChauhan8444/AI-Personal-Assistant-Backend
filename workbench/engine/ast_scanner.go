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
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// ASTField represents a field or parameter discovered via AST analysis.
type ASTField struct {
	Name       string `json:"name"`
	Type       string `json:"type"`
	Tag        string `json:"tag,omitempty"`
	JSONName   string `json:"json_name,omitempty"`
	Doc        string `json:"doc,omitempty"`
	IsExported bool   `json:"is_exported"`
	IsRequired bool   `json:"is_required"`
}

// ASTMethod represents an exported receiver method or function discovered via AST.
type ASTMethod struct {
	ID                  string     `json:"id"`
	Name                string     `json:"name"`
	Package             string     `json:"package"`
	Layer               string     `json:"layer"`
	Language            string     `json:"language"` // "go" | "python"
	Receiver            string     `json:"receiver,omitempty"`
	ReceiverRaw         string     `json:"receiver_raw,omitempty"`
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

// ASTType represents a struct, interface, class, or type definition.
type ASTType struct {
	Name       string     `json:"name"`
	Package    string     `json:"package"`
	Layer      string     `json:"layer"`
	Language   string     `json:"language"` // "go" | "python"
	Kind       string     `json:"kind"`     // "struct", "interface", "class", "type"
	Doc        string     `json:"doc"`
	Fields     []ASTField `json:"fields,omitempty"`
	Methods    []string   `json:"methods,omitempty"`
	FilePath   string     `json:"file_path"`
	LineNumber int        `json:"line_number"`
	IsExported bool       `json:"is_exported"`
}

// ASTPackage represents a scanned package or Python module directory.
type ASTPackage struct {
	Name      string      `json:"name"`
	RelPath   string      `json:"rel_path"`
	Layer     string      `json:"layer"`
	Language  string      `json:"language"`
	Doc       string      `json:"doc"`
	Files     []string    `json:"files"`
	Types     []ASTType   `json:"types"`
	Methods   []ASTMethod `json:"methods"`
	Functions []ASTMethod `json:"functions"`
}

// ASTScanSummary provides high-level discovery metrics across languages.
type ASTScanSummary struct {
	PackageCount    int            `json:"package_count"`
	FileCount       int            `json:"file_count"`
	TypeCount       int            `json:"type_count"`
	MethodCount     int            `json:"method_count"`
	FunctionCount   int            `json:"function_count"`
	CallableCount   int            `json:"callable_count"`
	IntegratedCount int            `json:"integrated_count"`
	GoCount         int            `json:"go_count"`
	PythonCount     int            `json:"python_count"`
	Layers          map[string]int `json:"layers"`
}

// ASTScanResult represents the complete scan outcome.
type ASTScanResult struct {
	ScannedAt  time.Time      `json:"scanned_at"`
	RootDir    string         `json:"root_dir"`
	Packages   []ASTPackage   `json:"packages"`
	AllMethods []ASTMethod    `json:"all_methods"`
	AllTypes   []ASTType      `json:"all_types"`
	Summary    ASTScanSummary `json:"summary"`
}

// FindSourceRoot discovers the relative or absolute path to the project's src directory.
func FindSourceRoot() string {
	for _, candidate := range []string{"src", "../src", "../../src", "../../../src"} {
		if info, err := os.Stat(candidate); err == nil && info.IsDir() {
			abs, err := filepath.Abs(candidate)
			if err == nil {
				return abs
			}
			return candidate
		}
	}
	return "src"
}

// DetermineLayer maps any relative or absolute file path to its architectural layer.
func DetermineLayer(path string) string {
	norm := filepath.ToSlash(path)
	switch {
	case strings.Contains(norm, "/gateway"):
		return "Layer 1: Ingress Gateway"
	case strings.Contains(norm, "/orchestrator"):
		return "Layer 2: Orchestration & Session"
	case strings.Contains(norm, "/tools"):
		return "Layer 3: Tool Engine"
	case strings.Contains(norm, "/bridge"):
		return "Layer 4: IPC & Bridge"
	case strings.Contains(norm, "/memory"):
		return "Layer 5: Memory Plane"
	case strings.Contains(norm, "/agents"):
		return "Layer 6: Autonomous Agents"
	case strings.Contains(norm, "/models"):
		return "Layer 7: Model Engine"
	default:
		return "System Core"
	}
}

// ASTScanner parses Go and Python source files and continuously watches for additions.
type ASTScanner struct {
	mu           sync.RWMutex
	rootDir      string
	lastResult   *ASTScanResult
	registry     *Registry
	watchCancel  context.CancelFunc
	fileModTimes map[string]time.Time
}

// NewASTScanner creates a scanner configured for the specified root source directory.
func NewASTScanner(rootDir string, reg *Registry) *ASTScanner {
	return &ASTScanner{
		rootDir:      rootDir,
		registry:     reg,
		fileModTimes: make(map[string]time.Time),
	}
}

// Scan parses all .go and .py files in rootDir.
func (s *ASTScanner) Scan() (*ASTScanResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	fset := token.NewFileSet()
	packagesMap := make(map[string]*ASTPackage)
	var goFiles []string
	var pyFiles []string
	newModTimes := make(map[string]time.Time)

	// Walk directory to discover all Go and Python files
	err := filepath.Walk(s.rootDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			name := info.Name()
			if strings.HasPrefix(name, ".") || name == "vendor" || name == "testdata" || name == "node_modules" || name == "__pycache__" {
				return filepath.SkipDir
			}
			return nil
		}

		newModTimes[path] = info.ModTime()

		if strings.HasSuffix(path, ".go") && !strings.HasSuffix(path, "_test.go") {
			goFiles = append(goFiles, path)
		} else if strings.HasSuffix(path, ".py") && !strings.HasSuffix(path, "_test.py") {
			pyFiles = append(pyFiles, path)
		}
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("error walking source directory: %w", err)
	}

	s.fileModTimes = newModTimes

	// 1. Parse Go AST
	for _, filePath := range goFiles {
		node, err := parser.ParseFile(fset, filePath, nil, parser.ParseComments)
		if err != nil {
			continue
		}

		pkgName := node.Name.Name
		dirPath := filepath.Dir(filePath)
		relDir, _ := filepath.Rel(s.rootDir, dirPath)
		if relDir == "" || relDir == "." {
			relDir = pkgName
		}

		pkgKey := "go:" + dirPath
		pkg, exists := packagesMap[pkgKey]
		if !exists {
			pkg = &ASTPackage{
				Name:      pkgName,
				RelPath:   filepath.ToSlash(relDir),
				Layer:     DetermineLayer(filePath),
				Language:  "go",
				Files:     make([]string, 0),
				Types:     make([]ASTType, 0),
				Methods:   make([]ASTMethod, 0),
				Functions: make([]ASTMethod, 0),
			}
			if node.Doc != nil {
				pkg.Doc = strings.TrimSpace(node.Doc.Text())
			}
			packagesMap[pkgKey] = pkg
		}

		relFile, _ := filepath.Rel(".", filePath)
		pkg.Files = append(pkg.Files, filepath.ToSlash(relFile))

		for _, decl := range node.Decls {
			switch d := decl.(type) {
			case *ast.GenDecl:
				s.inspectGoGenDecl(fset, d, filePath, pkg)
			case *ast.FuncDecl:
				s.inspectGoFuncDecl(fset, d, filePath, pkg)
			}
		}
	}

	// 2. Parse Python AST (Classes, Methods, Functions, Layer)
	for _, filePath := range pyFiles {
		dirPath := filepath.Dir(filePath)
		relDir, _ := filepath.Rel(s.rootDir, dirPath)
		if relDir == "" || relDir == "." {
			relDir = filepath.Base(s.rootDir)
		}

		pkgName := filepath.Base(dirPath)
		pkgKey := "py:" + dirPath
		pkg, exists := packagesMap[pkgKey]
		if !exists {
			pkg = &ASTPackage{
				Name:      pkgName,
				RelPath:   filepath.ToSlash(relDir),
				Layer:     DetermineLayer(filePath),
				Language:  "python",
				Files:     make([]string, 0),
				Types:     make([]ASTType, 0),
				Methods:   make([]ASTMethod, 0),
				Functions: make([]ASTMethod, 0),
			}
			packagesMap[pkgKey] = pkg
		}

		relFile, _ := filepath.Rel(".", filePath)
		pkg.Files = append(pkg.Files, filepath.ToSlash(relFile))

		s.inspectPythonFile(filePath, pkg)
	}

	// 3. Assemble and sort result
	result := &ASTScanResult{
		ScannedAt:  time.Now(),
		RootDir:    s.rootDir,
		Packages:   make([]ASTPackage, 0, len(packagesMap)),
		AllMethods: make([]ASTMethod, 0),
		AllTypes:   make([]ASTType, 0),
		Summary: ASTScanSummary{
			Layers: make(map[string]int),
		},
	}

	registeredMap := make(map[string]string)
	if s.registry != nil {
		for _, m := range s.registry.List() {
			registeredMap[strings.ToLower(m.ID)] = m.ID
			registeredMap[strings.ToLower(m.Name)] = m.ID
		}
	}

	for _, pkg := range packagesMap {
		sort.Slice(pkg.Types, func(i, j int) bool { return pkg.Types[i].Name < pkg.Types[j].Name })
		sort.Slice(pkg.Methods, func(i, j int) bool { return pkg.Methods[i].Name < pkg.Methods[j].Name })
		sort.Slice(pkg.Functions, func(i, j int) bool { return pkg.Functions[i].Name < pkg.Functions[j].Name })

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

	sort.Slice(result.Packages, func(i, j int) bool {
		return result.Packages[i].RelPath < result.Packages[j].RelPath
	})
	sort.Slice(result.AllMethods, func(i, j int) bool {
		return result.AllMethods[i].Signature < result.AllMethods[j].Signature
	})

	// Generate summary
	result.Summary.PackageCount = len(result.Packages)
	result.Summary.FileCount = len(goFiles) + len(pyFiles)
	result.Summary.GoCount = len(goFiles)
	result.Summary.PythonCount = len(pyFiles)
	result.Summary.TypeCount = len(result.AllTypes)

	for _, p := range result.Packages {
		result.Summary.MethodCount += len(p.Methods)
		result.Summary.FunctionCount += len(p.Functions)
		result.Summary.Layers[p.Layer] += len(p.Methods) + len(p.Functions)
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

// StartHotWatcher runs a background watcher that checks for file changes every interval.
// If any change is detected, it triggers a rescan, updates the registry, and broadcasts an SSE event.
func (s *ASTScanner) StartHotWatcher(interval time.Duration) {
	s.mu.Lock()
	if s.watchCancel != nil {
		s.watchCancel()
	}
	ctx, cancel := context.WithCancel(context.Background())
	s.watchCancel = cancel
	s.mu.Unlock()

	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				if s.hasDirectoryChanged() {
					res, err := s.Scan()
					if err == nil {
						added := s.AutoRegisterDiscoveredModules(s.registry)
						GlobalTelemetry.RecordGoLog(GoLogEntry{
							Timestamp: time.Now(),
							Level:     "INFO",
							Source:    "HotDetector",
							Message:   fmt.Sprintf("[HotDetection] Codebase change detected. Updated AST: %d packages, %d types, %d methods (+%d new).", res.Summary.PackageCount, res.Summary.TypeCount, res.Summary.MethodCount+res.Summary.FunctionCount, added),
						})
						GlobalTelemetry.BroadcastEvent("AST_RELOADED", res.Summary)
					}
				}
			}
		}
	}()
}

// StopHotWatcher halts the background file watcher.
func (s *ASTScanner) StopHotWatcher() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.watchCancel != nil {
		s.watchCancel()
		s.watchCancel = nil
	}
}

func (s *ASTScanner) hasDirectoryChanged() bool {
	s.mu.RLock()
	currentTimes := s.fileModTimes
	s.mu.RUnlock()

	changed := false
	scannedCount := 0

	_ = filepath.Walk(s.rootDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || changed {
			return nil
		}
		if info.IsDir() {
			name := info.Name()
			if strings.HasPrefix(name, ".") || name == "vendor" || name == "node_modules" || name == "__pycache__" {
				return filepath.SkipDir
			}
			return nil
		}
		if strings.HasSuffix(path, ".go") || strings.HasSuffix(path, ".py") {
			scannedCount++
			oldTime, exists := currentTimes[path]
			if !exists || !oldTime.Equal(info.ModTime()) {
				changed = true
			}
		}
		return nil
	})

	if !changed && scannedCount != len(currentTimes) {
		changed = true
	}

	return changed
}

func (s *ASTScanner) inspectGoGenDecl(fset *token.FileSet, decl *ast.GenDecl, filePath string, pkg *ASTPackage) {
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
			Layer:      pkg.Layer,
			Language:   "go",
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

func (s *ASTScanner) inspectGoFuncDecl(fset *token.FileSet, decl *ast.FuncDecl, filePath string, pkg *ASTPackage) {
	name := decl.Name.Name
	if !ast.IsExported(name) {
		return
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
		Layer:       pkg.Layer,
		Language:    "go",
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

// inspectPythonFile parses Python source files extracting classes, methods, docstrings, and type hints.
var (
	pyClassRegex = regexp.MustCompile(`^class\s+([A-Za-z0-9_]+)(?:\(([^)]*)\))?:`)
	pyFuncRegex  = regexp.MustCompile(`^(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(([\s\S]*?)\)(?:\s*->\s*([^:]+))?:`)
)

func splitPythonParams(raw string) []string {
	var parts []string
	depth := 0
	start := 0
	for i, ch := range raw {
		switch ch {
		case '[', '(', '{':
			depth++
		case ']', ')', '}':
			depth--
		case ',':
			if depth == 0 {
				p := strings.TrimSpace(raw[start:i])
				if p != "" {
					parts = append(parts, p)
				}
				start = i + 1
			}
		}
	}
	if start < len(raw) {
		p := strings.TrimSpace(raw[start:])
		if p != "" {
			parts = append(parts, p)
		}
	}
	return parts
}

func (s *ASTScanner) inspectPythonFile(filePath string, pkg *ASTPackage) {
	content, err := os.ReadFile(filePath)
	if err != nil {
		return
	}

	lines := strings.Split(string(content), "\n")
	lineNum := 0
	var currentClass *ASTType
	inDocstring := false
	docstringBuf := strings.Builder{}

	for lineNum < len(lines) {
		line := lines[lineNum]
		lineNum++
		trimmed := strings.TrimSpace(line)

		// Simple docstring collector
		if strings.HasPrefix(trimmed, `"""`) || strings.HasPrefix(trimmed, `'''`) {
			if inDocstring {
				inDocstring = false
			} else {
				inDocstring = true
				docstringBuf.Reset()
				docstringBuf.WriteString(strings.Trim(trimmed, `"'`))
				if strings.Count(trimmed, `"""`) >= 2 || strings.Count(trimmed, `'''`) >= 2 {
					inDocstring = false
				}
				continue
			}
		} else if inDocstring {
			docstringBuf.WriteString(" " + trimmed)
			continue
		}

		// Class match
		if match := pyClassRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			className := match[1]
			isExported := !strings.HasPrefix(className, "_")
			cDoc := strings.TrimSpace(docstringBuf.String())

			pyType := ASTType{
				Name:       className,
				Package:    pkg.Name,
				Layer:      pkg.Layer,
				Language:   "python",
				Kind:       "class",
				Doc:        cDoc,
				FilePath:   filepath.ToSlash(filePath),
				LineNumber: lineNum,
				IsExported: isExported,
				Methods:    make([]string, 0),
			}
			pkg.Types = append(pkg.Types, pyType)
			currentClass = &pkg.Types[len(pkg.Types)-1]
			continue
		}

		// Function or method start (handle multiline function definitions)
		if strings.HasPrefix(trimmed, "def ") || strings.HasPrefix(trimmed, "async def ") {
			startLine := lineNum
			isMethod := currentClass != nil && strings.HasPrefix(line, "    ")
			fullDef := trimmed

			for !strings.HasSuffix(strings.TrimSpace(fullDef), ":") && lineNum < len(lines) {
				fullDef += " " + strings.TrimSpace(lines[lineNum])
				lineNum++
			}

			if match := pyFuncRegex.FindStringSubmatch(fullDef); len(match) > 1 {
				fnName := match[1]
				if strings.HasPrefix(fnName, "__") && fnName != "__init__" {
					continue
				}

				rawParams := strings.TrimSpace(match[2])
				rawReturn := strings.TrimSpace(match[3])

				params := make([]ASTField, 0)
				if rawParams != "" {
					parts := splitPythonParams(rawParams)
					for _, part := range parts {
						part = strings.TrimSpace(part)
						if part == "" || part == "self" || part == "cls" {
							continue
						}
						pTokens := strings.SplitN(part, ":", 2)
						pName := strings.TrimSpace(pTokens[0])
						pType := "Any"
						if len(pTokens) > 1 {
							// Strip default value if present
							typeAndDef := strings.SplitN(pTokens[1], "=", 2)
							pType = strings.TrimSpace(typeAndDef[0])
						}
						params = append(params, ASTField{
							Name:       pName,
							Type:       pType,
							IsExported: true,
							IsRequired: !strings.Contains(part, "="),
						})
					}
				}

				returns := []string{}
				if rawReturn != "" {
					returns = append(returns, rawReturn)
				}

				recv := ""
				recvRaw := ""
				id := fmt.Sprintf("%s.%s", pkg.Name, fnName)
				if isMethod {
					recv = currentClass.Name
					recvRaw = currentClass.Name
					id = fmt.Sprintf("%s.%s.%s", pkg.Name, recvRaw, fnName)
					currentClass.Methods = append(currentClass.Methods, fnName)
				}

				sig := fmt.Sprintf("def %s(%s)", fnName, rawParams)
				if rawReturn != "" {
					sig += " -> " + rawReturn
				}

				method := ASTMethod{
					ID:          id,
					Name:        fnName,
					Package:     pkg.Name,
					Layer:       pkg.Layer,
					Language:    "python",
					Receiver:    recv,
					ReceiverRaw: recvRaw,
					Signature:   sig,
					Doc:         strings.TrimSpace(docstringBuf.String()),
					Params:      params,
					Returns:     returns,
					FilePath:    filepath.ToSlash(filePath),
					LineNumber:  startLine,
					IsCallable:  !strings.HasPrefix(fnName, "_"),
				}

				if isMethod {
					pkg.Methods = append(pkg.Methods, method)
				} else {
					pkg.Functions = append(pkg.Functions, method)
				}
			}
		}
	}
}

func (s *ASTScanner) matchRegisteredRunner(m *ASTMethod, registeredMap map[string]string) {
	nameLower := strings.ToLower(m.Name)
	recvLower := strings.ToLower(m.ReceiverRaw)
	pkgLower := strings.ToLower(m.Package)

	for key, regID := range registeredMap {
		if strings.Contains(key, nameLower) && (recvLower == "" || strings.Contains(key, recvLower) || strings.Contains(key, pkgLower)) {
			m.HasRegisteredRunner = true
			m.RegisteredModuleID = regID
			return
		}
	}
}

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

func layerToKey(layerStr string) string {
	l := strings.ToLower(layerStr)
	switch {
	case strings.Contains(l, "layer 1"):
		return "layer1"
	case strings.Contains(l, "layer 2"):
		return "layer2"
	case strings.Contains(l, "layer 3"):
		return "layer3"
	case strings.Contains(l, "layer 4"):
		return "layer4"
	case strings.Contains(l, "layer 5"):
		return "layer5"
	case strings.Contains(l, "layer 6"):
		return "layer6"
	case strings.Contains(l, "layer 7"):
		return "layer7"
	default:
		return "system"
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
		if !m.IsCallable || m.HasRegisteredRunner {
			continue
		}

		// Filter out noisy internal methods and low-level CLI rendering helpers
		nameLower := strings.ToLower(m.Name)
		if strings.HasPrefix(m.Name, "_") ||
			strings.Contains(nameLower, "render") ||
			strings.Contains(nameLower, "repl") ||
			strings.Contains(nameLower, "interactive") {
			continue
		}

		modID := fmt.Sprintf("ast:%s", strings.ToLower(m.ID))
		if _, exists := reg.Get(modID); exists {
			continue
		}

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
			desc = fmt.Sprintf("[%s] %s discovered from %s:%d (%s)", strings.ToUpper(m.Language), m.Signature, m.FilePath, m.LineNumber, m.Layer)
		}

		mod := Module{
			ID:          modID,
			Name:        fmt.Sprintf("[%s] %s", strings.ToUpper(m.Language), m.ID),
			Tier:        "GRANULAR_AST",
			Layer:       layerToKey(m.Layer),
			Category:    fmt.Sprintf("AST: %s (%s)", m.Package, m.Layer),
			Description: desc,
			Schema: ModuleSchema{
				TypeName: m.ID,
				Fields:   fields,
			},
			Presets: []Preset{
				{
					ID:          "ast-default",
					Name:        fmt.Sprintf("AST Inspect: %s", m.Name),
					Category:    "AST Introspection",
					Description: fmt.Sprintf("Parameters and signature for %s", m.Signature),
					Payload:     map[string]any{"_language": m.Language, "_layer": m.Layer, "_signature": m.Signature, "_file": m.FilePath, "_line": m.LineNumber},
				},
			},
			Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- StreamEvent) (any, error) {
				stream <- StreamEvent{
					Index:     1,
					Timestamp: time.Now(),
					Type:      "AST_INSPECT",
					AgentName: "ASTScanner",
					Payload: map[string]any{
						"language":  m.Language,
						"layer":     m.Layer,
						"signature": m.Signature,
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
					"language":           m.Language,
					"layer":              m.Layer,
					"message":            fmt.Sprintf("[%s] %s verified at %s:%d", strings.ToUpper(m.Language), m.Signature, m.FilePath, m.LineNumber),
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
