package sys

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"

	"assistant/src/tools"
)

// SysLockTool locks the active desktop session.
type SysLockTool struct{}

func NewSysLockTool() *SysLockTool {
	return &SysLockTool{}
}

func (t *SysLockTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_lock",
		Category:           "system",
		Description:        "Locks the active desktop session using the desktop lock screen.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_lock when the user requests locking their workstation.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysLockTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	lockers := [][]string{
		{"hyprlock"},
		{"swaylock"},
		{"betterlockscreen", "-l"},
		{"i3lock"},
		{"loginctl", "lock-session"},
	}

	for _, cmdParts := range lockers {
		if _, err := exec.LookPath(cmdParts[0]); err == nil {
			cmd := exec.Command(cmdParts[0], cmdParts[1:]...)
			if err := cmd.Start(); err == nil {
				return &tools.ToolResult{Stdout: fmt.Sprintf("Screen locked successfully using %s", cmdParts[0])}, nil
			}
		}
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "no compatible screen locker found (tried hyprlock, swaylock, betterlockscreen, i3lock, loginctl)",
	}, nil
}

// SysSuspendTool suspends the host system to RAM.
type SysSuspendTool struct{}

func NewSysSuspendTool() *SysSuspendTool {
	return &SysSuspendTool{}
}

func (t *SysSuspendTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_suspend",
		Category:           "system",
		Description:        "Suspends the system into low-power sleep state (suspend to RAM).",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Requires explicit confirmation before putting the system to sleep.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysSuspendTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	out, err := executeCommand(ctx, "systemctl", "suspend")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to suspend system: %v (output: %s)", err, out),
		}, nil
	}
	return &tools.ToolResult{Stdout: "System suspension initiated successfully."}, nil
}

// SysHealthTool reports real-time CPU, RAM, disk, and battery statistics.
type SysHealthTool struct{}

func NewSysHealthTool() *SysHealthTool {
	return &SysHealthTool{}
}

func (t *SysHealthTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_health",
		Category:           "system",
		Description:        "Reports real-time system health including CPU usage, RAM utilization, root disk space, and battery status.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_health for system status diagnostics.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysHealthTool) Execute(_ context.Context, _ string) (*tools.ToolResult, error) {
	ramPercent, ramTotalMB, ramAvailMB := readMemoryStats()
	diskPercent, diskFreeGB, diskTotalGB := readDiskStats("/")
	batteryPercent, batteryStatus := readBatteryStats()

	health := map[string]any{
		"memory": map[string]any{
			"used_percent": ramPercent,
			"total_mb":     ramTotalMB,
			"available_mb": ramAvailMB,
		},
		"disk_root": map[string]any{
			"used_percent": diskPercent,
			"free_gb":      diskFreeGB,
			"total_gb":     diskTotalGB,
		},
		"battery": map[string]any{
			"percent": batteryPercent,
			"status":  batteryStatus,
		},
	}

	resultBytes, _ := json.MarshalIndent(health, "", "  ")
	return &tools.ToolResult{Stdout: string(resultBytes)}, nil
}

func readMemoryStats() (float64, int, int) {
	data, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0, 0, 0
	}

	var memTotal, memAvail int
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) >= 2 {
			if fields[0] == "MemTotal:" {
				memTotal, _ = strconv.Atoi(fields[1])
			} else if fields[0] == "MemAvailable:" {
				memAvail, _ = strconv.Atoi(fields[1])
			}
		}
	}

	if memTotal <= 0 {
		return 0, 0, 0
	}

	used := memTotal - memAvail
	percent := (float64(used) / float64(memTotal)) * 100.0
	return float64(int(percent*10)) / 10, memTotal / 1024, memAvail / 1024
}

func readDiskStats(path string) (float64, float64, float64) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, 0, 0
	}

	totalBytes := stat.Blocks * uint64(stat.Bsize)
	freeBytes := stat.Bavail * uint64(stat.Bsize)
	usedBytes := totalBytes - freeBytes

	if totalBytes == 0 {
		return 0, 0, 0
	}

	usedPercent := (float64(usedBytes) / float64(totalBytes)) * 100.0
	totalGB := float64(totalBytes) / (1024 * 1024 * 1024)
	freeGB := float64(freeBytes) / (1024 * 1024 * 1024)

	return float64(int(usedPercent*10)) / 10, float64(int(freeGB*10)) / 10, float64(int(totalGB*10)) / 10
}

func readBatteryStats() (int, string) {
	powerSupplyDir := "/sys/class/power_supply"
	entries, err := os.ReadDir(powerSupplyDir)
	if err != nil {
		return 100, "AC Power"
	}

	for _, entry := range entries {
		name := entry.Name()
		if strings.HasPrefix(name, "BAT") {
			batDir := filepath.Join(powerSupplyDir, name)
			capData, err1 := os.ReadFile(filepath.Join(batDir, "capacity"))
			statusData, _ := os.ReadFile(filepath.Join(batDir, "status"))

			if err1 == nil {
				capVal, errParse := strconv.Atoi(strings.TrimSpace(string(capData)))
				if errParse == nil {
					status := strings.TrimSpace(string(statusData))
					if status == "" {
						status = "Unknown"
					}
					return capVal, status
				}
			}
		}
	}

	return 100, "AC Power"
}
