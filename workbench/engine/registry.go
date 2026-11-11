package engine

import (
	"encoding/json"
	"fmt"
	"reflect"
	"sort"
	"strings"
	"sync"
	"time"
)

// Registry manages registered modules and introspected schemas.
type Registry struct {
	mu      sync.RWMutex
	modules map[string]Module
}

// GlobalRegistry is the default singleton registry.
var GlobalRegistry = NewRegistry()

// NewRegistry initializes an empty Module Registry.
func NewRegistry() *Registry {
	return &Registry{
		modules: make(map[string]Module),
	}
}

// Register adds a module to the registry, automatically inspecting its input schema if empty.
func (r *Registry) Register(mod Module) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if mod.Schema.TypeName == "" && mod.InputType != nil {
		mod.Schema = IntrospectType(mod.InputType)
	}

	r.modules[mod.ID] = mod
}

// Get retrieves a registered module by its ID.
func (r *Registry) Get(id string) (Module, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	mod, exists := r.modules[id]
	return mod, exists
}

// List returns all registered modules sorted by category and name.
func (r *Registry) List() []Module {
	r.mu.RLock()
	defer r.mu.RUnlock()

	list := make([]Module, 0, len(r.modules))
	for _, m := range r.modules {
		list = append(list, m)
	}

	sort.Slice(list, func(i, j int) bool {
		if list[i].Category != list[j].Category {
			return list[i].Category < list[j].Category
		}
		return list[i].Name < list[j].Name
	})

	return list
}

// IntrospectType extracts parameter metadata from a reflect.Type.
func IntrospectType(t reflect.Type) ModuleSchema {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}

	schema := ModuleSchema{
		TypeName: t.String(),
		Fields:   make([]FieldSchema, 0),
	}

	if t.Kind() != reflect.Struct {
		schema.Fields = append(schema.Fields, FieldSchema{
			Name:     "input",
			Type:     t.String(),
			Required: true,
		})
		return schema
	}

	schema.Fields = introspectStructFields(t)
	return schema
}

func introspectStructFields(t reflect.Type) []FieldSchema {
	fields := make([]FieldSchema, 0, t.NumField())

	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		if !f.IsExported() {
			continue
		}

		jsonTag := f.Tag.Get("json")
		if jsonTag == "-" {
			continue
		}

		name := f.Name
		required := true
		if jsonTag != "" {
			parts := strings.Split(jsonTag, ",")
			if parts[0] != "" {
				name = parts[0]
			}
			for _, p := range parts[1:] {
				if p == "omitempty" {
					required = false
				}
			}
		}

		desc := f.Tag.Get("desc")
		enumTag := f.Tag.Get("enum")
		var enums []string
		if enumTag != "" {
			enums = strings.Split(enumTag, ",")
			for idx := range enums {
				enums[idx] = strings.TrimSpace(enums[idx])
			}
		}

		ft := f.Type
		for ft.Kind() == reflect.Pointer {
			ft = ft.Elem()
			required = false
		}

		fieldSchema := FieldSchema{
			Name:        name,
			Type:        formatTypeName(ft),
			Required:    required,
			Description: desc,
			Enum:        enums,
			Default:     generateDefaultValue(ft),
		}

		if ft.Kind() == reflect.Struct && ft != reflect.TypeOf(time.Time{}) {
			fieldSchema.Fields = introspectStructFields(ft)
		}

		fields = append(fields, fieldSchema)
	}

	return fields
}

func formatTypeName(t reflect.Type) string {
	switch t.Kind() {
	case reflect.Slice:
		return "[]" + formatTypeName(t.Elem())
	case reflect.Map:
		return fmt.Sprintf("map[%s]%s", formatTypeName(t.Key()), formatTypeName(t.Elem()))
	case reflect.Struct:
		if t == reflect.TypeOf(time.Time{}) {
			return "time.Time (ISO-8601)"
		}
		return t.Name()
	default:
		return t.String()
	}
}

func generateDefaultValue(t reflect.Type) any {
	switch t.Kind() {
	case reflect.String:
		return ""
	case reflect.Bool:
		return false
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return 0
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return 0
	case reflect.Float32, reflect.Float64:
		return 0.0
	case reflect.Slice:
		return []any{}
	case reflect.Map:
		return map[string]any{}
	default:
		return nil
	}
}

// GenerateDefaultJSON generates a formatted JSON template from an input struct type.
func GenerateDefaultJSON(t reflect.Type) string {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	val := reflect.New(t).Interface()
	b, err := json.MarshalIndent(val, "", "  ")
	if err != nil {
		return "{}"
	}
	return string(b)
}
