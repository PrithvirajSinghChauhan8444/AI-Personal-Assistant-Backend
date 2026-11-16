package hyprland

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"time"

	"assistant/src/tools"
)

var (
	luaConfigOnce sync.Once
	isLuaDetected bool
)

// checkHyprlandBinary verifies that hyprctl is installed and executable in PATH.
func checkHyprlandBinary() error {
	if _, err := exec.LookPath("hyprctl"); err != nil {
		return fmt.Errorf("hyprctl binary not found in PATH (Hyprland may not be installed): %w", err)
	}
	return nil
}

// executeHyprctl executes hyprctl with context timeout and returns combined stdout/stderr.
func executeHyprctl(ctx context.Context, args ...string) (string, error) {
	if err := checkHyprlandBinary(); err != nil {
		return "", err
	}

	cmdCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, "hyprctl", args...)
	out, err := cmd.CombinedOutput()
	outputStr := strings.TrimSpace(string(out))
	if err != nil {
		return outputStr, fmt.Errorf("hyprctl %s failed: %w (output: %s)", strings.Join(args, " "), err, outputStr)
	}
	return outputStr, nil
}

// isLuaConfigProvider checks whether Hyprland is operating with Lua configuration.
func isLuaConfigProvider(ctx context.Context) bool {
	luaConfigOnce.Do(func() {
		out, err := executeHyprctl(ctx, "status")
		if err == nil && strings.Contains(out, "configProvider: lua") {
			isLuaDetected = true
		}
	})
	return isLuaDetected
}

// executeHyprDispatch dispatches a Hyprland command seamlessly on both classic and Lua environments.
func executeHyprDispatch(ctx context.Context, dispatcher string, args string) (*tools.ToolResult, error) {
	dispatcher = strings.TrimSpace(dispatcher)
	args = strings.TrimSpace(args)

	isLua := isLuaConfigProvider(ctx)

	// If the dispatcher is already a Lua expression (starts with hl. or contains parens)
	if strings.HasPrefix(dispatcher, "hl.") || strings.Contains(dispatcher, "(") {
		out, err := executeHyprctl(ctx, "dispatch", dispatcher)
		if err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("hyprctl dispatch lua error: %v", err),
			}, nil
		}
		return &tools.ToolResult{Stdout: out}, nil
	}

	// In Lua configuration mode, convert canonical classic dispatchers to Lua HL.Dispatcher calls
	if isLua {
		var luaExpr string
		switch strings.ToLower(dispatcher) {
		case "workspace":
			luaExpr = fmt.Sprintf("hl.dsp.workspace.change_id({workspace = %q})", args)
		case "movetoworkspace":
			luaExpr = fmt.Sprintf("hl.dsp.workspace.move({workspace = %q})", args)
		case "movetoworkspacesilent":
			luaExpr = fmt.Sprintf("hl.dsp.workspace.move({workspace = %q, silent = true})", args)
		case "focuswindow":
			luaExpr = fmt.Sprintf("hl.dsp.focus({window = %q})", args)
		case "closewindow":
			if args != "" {
				luaExpr = fmt.Sprintf("hl.dsp.window.close({window = %q})", args)
			} else {
				luaExpr = "hl.dsp.window.close()"
			}
		case "killactive":
			luaExpr = "hl.dsp.window.close()"
		case "togglefloating":
			luaExpr = "hl.dsp.window.float()"
		case "fullscreen":
			luaExpr = "hl.dsp.window.fullscreen()"
		case "pin":
			luaExpr = "hl.dsp.window.pin()"
		case "centerwindow":
			luaExpr = "hl.dsp.window.center()"
		case "cyclenext":
			luaExpr = "hl.dsp.window.cycle_next()"
		case "movewindow":
			luaExpr = fmt.Sprintf("hl.dsp.window.move({direction = %q})", args)
		case "movefocus":
			luaExpr = fmt.Sprintf("hl.dsp.window.move({direction = %q})", args)
		case "exec":
			luaExpr = fmt.Sprintf("hl.dsp.exec_cmd(%q)", args)
		default:
			// Fallback: try raw dispatch args
			cmdArgs := []string{"dispatch", dispatcher}
			if args != "" {
				cmdArgs = append(cmdArgs, args)
			}
			out, err := executeHyprctl(ctx, cmdArgs...)
			if err == nil {
				return &tools.ToolResult{Stdout: out}, nil
			}
			// If error mentions lua shorthand, format as hl.dsp.<dispatcher> call
			luaExpr = fmt.Sprintf("hl.dsp.%s(%q)", dispatcher, args)
		}

		out, err := executeHyprctl(ctx, "dispatch", luaExpr)
		if err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("dispatch failed: %v", err),
			}, nil
		}
		return &tools.ToolResult{Stdout: out}, nil
	}

	// Classic hyprland.conf environment
	cmdArgs := []string{"dispatch", dispatcher}
	if args != "" {
		cmdArgs = append(cmdArgs, args)
	}
	out, err := executeHyprctl(ctx, cmdArgs...)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("dispatch failed: %v", err),
		}, nil
	}
	return &tools.ToolResult{Stdout: out}, nil
}
