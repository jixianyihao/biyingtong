// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

/// Tracks the Flask sidecar child so we can terminate it on window close.
struct FlaskSidecar(Mutex<Option<Child>>);

fn spawn_flask() -> Option<Child> {
    // Only spawn in release builds; in dev mode the user runs `python app.py` manually.
    #[cfg(debug_assertions)]
    {
        return None;
    }

    // In release, the Flask sidecar binary is bundled next to the exe. For MVP we
    // assume python is on PATH — later bundles may ship a PyInstaller exe.
    #[allow(unreachable_code)]
    let path = std::env::current_exe()
        .ok()?
        .parent()?
        .join("..")
        .join("..")
        .join("..")
        .join("app.py");
    Command::new("python")
        .arg(path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(FlaskSidecar(Mutex::new(spawn_flask())))
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<FlaskSidecar>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
