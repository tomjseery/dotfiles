package utils

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestRegisteredShellIsolation(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	bin := filepath.Join(home, "bin")
	os.MkdirAll(bin, 0755)
	log := filepath.Join(home, "calls")
	t.Setenv("CALL_LOG", log)
	for _, name := range []string{"qs", "pkill", "caelestia", "whisker", "hyprctl"} {
		body := "#!/bin/sh\nprintf '%s\\n' '" + name + "'\" $*\" >> \"$CALL_LOG\"\n"
		if err := os.WriteFile(filepath.Join(bin, name), []byte(body), 0755); err != nil {
			t.Fatal(err)
		}
	}
	t.Setenv("PATH", bin+":"+os.Getenv("PATH"))
	for _, name := range []string{"first", "second"} {
		path := filepath.Join(home, ".config", "quickshell", name)
		os.MkdirAll(path, 0755)
		os.WriteFile(filepath.Join(path, "shell.qml"), []byte("import Quickshell\nShellRoot {}"), 0644)
	}
	personal := filepath.Join(home, ".config", "hypr", "personal.lua")
	os.MkdirAll(filepath.Dir(personal), 0755)
	os.WriteFile(personal, []byte("-- preserve my settings"), 0644)
	config := Config{Flavours: []string{"first", "second"}, Keybinds: map[string]string{"second": "default"}, PanelKeybind: "SUPER + CTRL + SHIFT + Tab"}
	ApplyFlavour("second", config, false)
	wantStart := "qs --path " + filepath.Join(home, ".config/quickshell/second")
	var calls string
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		data, _ := os.ReadFile(log)
		calls = string(data)
		if strings.Contains(calls, wantStart+"\n") {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	for _, name := range config.Flavours {
		want := "qs --path " + filepath.Join(home, ".config/quickshell", name) + " kill"
		if !strings.Contains(calls, want) {
			t.Errorf("missing targeted stop %q in %s", want, calls)
		}
	}
	if !strings.Contains(calls, wantStart+"\n") {
		t.Errorf("missing launch: %s", calls)
	}
	for _, forbidden := range []string{"pkill", "caelestia", "whisker"} {
		if strings.Contains(calls, forbidden) {
			t.Errorf("unrelated process action: %s", calls)
		}
	}
	data, _ := os.ReadFile(personal)
	if string(data) != "-- preserve my settings" {
		t.Fatal("personal configuration changed")
	}
}

func TestExternalSymlinkedShell(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	external := t.TempDir()
	os.WriteFile(filepath.Join(external, "shell.qml"), []byte("import Quickshell\nShellRoot {}"), 0644)
	root := filepath.Join(home, ".config", "quickshell")
	os.MkdirAll(root, 0755)
	link := filepath.Join(root, "external")
	if err := os.Symlink(external, link); err != nil {
		t.Fatal(err)
	}
	path, ok := GetFlavourPath("external")
	if !ok || path != link {
		t.Fatalf("external shell not detected: %q %v", path, ok)
	}
}
