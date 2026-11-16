package hyprland

import "assistant/src/tools"

// GetAllHyprlandTools returns all canonical Hyprland window manager controller tools.
func GetAllHyprlandTools() []tools.Tool {
	return []tools.Tool{
		NewHyprGetActiveWindowTool(),
		NewHyprGetWorkspacesTool(),
		NewHyprGetClientsTool(),
		NewHyprGetMonitorsTool(),
		NewHyprDispatchTool(),
		NewHyprSwitchWorkspaceTool(),
		NewHyprMoveWindowTool(),
		NewHyprFocusWindowTool(),
		NewHyprWindowActionTool(),
		NewHyprCloseWindowTool(),
		NewHyprNotifyTool(),
		NewHyprKeywordTool(),
	}
}
