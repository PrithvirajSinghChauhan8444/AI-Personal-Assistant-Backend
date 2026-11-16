package dispatcher

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"assistant/src/mcp"
	"assistant/src/tools"
	"assistant/src/tools/browser"
	"assistant/src/tools/fs"
	"assistant/src/tools/git"
	"assistant/src/tools/hyprland"
	"assistant/src/tools/net"
	"assistant/src/tools/sys"
	"assistant/src/tools/workspace"
)

// RegisterAllTools instantiates and registers all canonical system, filesystem, git, net, workspace, and MCP tools.
func RegisterAllTools(registry *tools.ToolRegistry, configDir string) error {
	if registry == nil {
		return fmt.Errorf("registry cannot be nil")
	}

	googleClient := workspace.NewGoogleClient(configDir)

	allTools := []tools.Tool{
		// System Category
		sys.NewSysExecTool(),
		sys.NewSysPsTool(),
		sys.NewSysKillTool(),
		sys.NewSysVolumeGetTool(),
		sys.NewSysVolumeSetTool(),
		sys.NewSysVolumeMuteTool(),
		sys.NewSysBrightnessGetTool(),
		sys.NewSysBrightnessSetTool(),
		sys.NewSysLockTool(),
		sys.NewSysSuspendTool(),
		sys.NewSysHealthTool(),
		sys.NewSysClipboardCopyTool(),
		sys.NewSysClipboardPasteTool(),
		sys.NewSysLaunchAppTool(),
		sys.NewSysGetTimeTool(),
		sys.NewSysExecPythonTool(),

		// Filesystem Category
		fs.NewFsReadTool(),
		fs.NewFsWriteTool(),
		fs.NewFsDeleteTool(),
		fs.NewFsListTool(),
		fs.NewFsRipgrepTool(),
		fs.NewDocParseTool(),
		fs.NewAudioTranscribeTool(),

		// Git Category
		git.NewGitStatusTool(),
		git.NewGitDiffTool(),
		git.NewGitCommitTool(),

		// Net Category
		net.NewNetFetchTool(),
		net.NewNetSearchTool(),
		net.NewNetWeatherTool(),

		// Workspace Category
		workspace.NewGmailListTool(googleClient),
		workspace.NewGmailReadTool(googleClient),
		workspace.NewGmailSendDraftTool(googleClient),
		workspace.NewGmailSendTool(googleClient),
		workspace.NewGmailReplyTool(googleClient),
		workspace.NewGmailCheckUnreadTool(googleClient),
		workspace.NewCalendarListTool(googleClient),
		workspace.NewCalendarCreateEventTool(googleClient),
		workspace.NewCalendarEditEventTool(googleClient),
		workspace.NewCalendarDeleteEventTool(googleClient),
		workspace.NewTasksListTool(googleClient),
		workspace.NewTasksCreateTool(googleClient),
		workspace.NewClassroomListCoursesTool(googleClient),
		workspace.NewClassroomListAssignmentsTool(googleClient),
		workspace.NewClassroomGetAssignmentTool(googleClient),
		workspace.NewClassroomListAnnouncementsTool(googleClient),
		workspace.NewGoogleAuthLoginTool(configDir),
	}

	allTools = append(allTools, browser.GetAllBrowserTools(nil)...)
	allTools = append(allTools, hyprland.GetAllHyprlandTools()...)

	for _, t := range allTools {
		if err := registry.Register(t); err != nil {
			return fmt.Errorf("failed to register tool %q: %w", t.Metadata().Name, err)
		}
	}

	return nil
}

// RegisterMCPTools initializes the MCP Hub from mcp_servers.json (if present) and registers its tools.
func RegisterMCPTools(ctx context.Context, registry *tools.ToolRegistry, configDir string) (*mcp.Hub, error) {
	if registry == nil {
		return nil, fmt.Errorf("registry cannot be nil")
	}

	mcpPath := filepath.Join(configDir, "mcp_servers.json")
	if _, err := os.Stat(mcpPath); os.IsNotExist(err) {
		return nil, nil
	}

	cfg, err := mcp.LoadConfigFile(mcpPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load mcp config: %w", err)
	}

	hub := mcp.NewHub(cfg)
	if err := hub.StartAll(ctx); err != nil {
		return hub, fmt.Errorf("error starting mcp hub servers: %w", err)
	}

	if err := hub.RegisterAllTools(registry); err != nil {
		return hub, fmt.Errorf("error registering mcp tools: %w", err)
	}

	return hub, nil
}
