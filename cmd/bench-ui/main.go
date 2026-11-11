package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"assistant/workbench"
)

func main() {
	port := flag.Int("port", 8080, "Port to run the workbench server on")
	historyDir := flag.String("history-dir", filepath.Join("workspace", "workbench"), "Directory for flight recorder logs")
	flag.Parse()

	if err := workbench.Start(*port, *historyDir); err != nil {
		fmt.Fprintf(os.Stderr, "Fatal error: %v\n", err)
		os.Exit(1)
	}
}
