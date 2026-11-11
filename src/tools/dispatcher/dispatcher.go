package dispatcher

import (
	"fmt"

	"assistant/src/tools"
	"assistant/src/tools/tools/fs"
	"assistant/src/tools/tools/git"
	"assistant/src/tools/tools/net"
	"assistant/src/tools/tools/sys"
	"assistant/src/tools/tools/workspace"
)

// RegisterAllTools instantiates and registers all canonical system, filesystem, git, net, and workspace tools.
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

		// Filesystem Category
		fs.NewFsReadTool(),
		fs.NewFsWriteTool(),
		fs.NewFsDeleteTool(),
		fs.NewFsListTool(),
		fs.NewFsRipgrepTool(),

		// Git Category
		git.NewGitStatusTool(),
		git.NewGitDiffTool(),
		git.NewGitCommitTool(),

		// Net Category
		net.NewNetFetchTool(),
		net.NewNetSearchTool(),

		// Workspace Category
		workspace.NewGmailListTool(googleClient),
		workspace.NewGmailReadTool(googleClient),
		workspace.NewGmailSendDraftTool(googleClient),
		workspace.NewCalendarListTool(googleClient),
	}

	for _, t := range allTools {
		if err := registry.Register(t); err != nil {
			return fmt.Errorf("failed to register tool %q: %w", t.Metadata().Name, err)
		}
	}

	return nil
}
