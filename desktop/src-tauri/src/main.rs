use std::{
    env,
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{TcpStream, ToSocketAddrs},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::Duration,
};

const FASTAPI_HOST: &str = "127.0.0.1";
const FASTAPI_PORT: u16 = 8710;

fn main() {
    tauri::Builder::default()
        .setup(|_app| {
            ensure_local_fastapi_on_app_open();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running stock-MING Command Center 3.0");
}

fn ensure_local_fastapi_on_app_open() {
    thread::spawn(|| {
        let Some(project_root) = resolve_project_root() else {
            return;
        };
        append_autostart_log(
            &project_root,
            "tauri app opened; checking local FastAPI health before autostart",
        );

        if local_fastapi_ready() {
            append_autostart_log(
                &project_root,
                "local FastAPI already ready; no backend process spawned",
            );
            return;
        }

        match spawn_local_fastapi(&project_root) {
            Ok(pid) => append_autostart_log(
                &project_root,
                &format!("spawned local FastAPI process pid={pid}"),
            ),
            Err(error) => {
                append_autostart_log(
                    &project_root,
                    &format!("failed to spawn local FastAPI safely: {error}"),
                );
                return;
            }
        }

        for _ in 0..40 {
            if local_fastapi_ready() {
                append_autostart_log(
                    &project_root,
                    "local FastAPI health ready after Tauri autostart",
                );
                return;
            }
            thread::sleep(Duration::from_millis(500));
        }

        append_autostart_log(
            &project_root,
            "local FastAPI still warming up after Tauri autostart wait window",
        );
    });
}

fn resolve_project_root() -> Option<PathBuf> {
    if let Ok(value) = env::var("COMMAND_CENTER_3_PROJECT_ROOT") {
        let candidate = PathBuf::from(value);
        if is_project_root(&candidate) {
            return Some(candidate);
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    if let Some(candidate) = manifest_dir.parent().and_then(Path::parent) {
        let candidate = candidate.to_path_buf();
        if is_project_root(&candidate) {
            return Some(candidate);
        }
    }

    if let Ok(mut candidate) = env::current_dir() {
        loop {
            if is_project_root(&candidate) {
                return Some(candidate);
            }
            if !candidate.pop() {
                break;
            }
        }
    }

    None
}

fn is_project_root(path: &Path) -> bool {
    path.join("server/main.py").is_file() && path.join("desktop/src-tauri/tauri.conf.json").is_file()
}

fn python_executable(project_root: &Path) -> PathBuf {
    if let Ok(value) = env::var("STOCK_MING_PYTHON") {
        if !value.trim().is_empty() {
            return PathBuf::from(value);
        }
    }

    let venv_python = project_root.join(".venv/bin/python");
    if venv_python.is_file() {
        return venv_python;
    }

    PathBuf::from("python3")
}

fn local_fastapi_ready() -> bool {
    let Some(addr) = format!("{FASTAPI_HOST}:{FASTAPI_PORT}")
        .to_socket_addrs()
        .ok()
        .and_then(|mut addrs| addrs.next())
    else {
        return false;
    };

    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(800)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1200)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));
    if stream
        .write_all(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1:8710\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    local_fastapi_health_body_ready(&response)
}

fn local_fastapi_health_body_ready(response: &str) -> bool {
    let compact: String = response.chars().filter(|ch| !ch.is_ascii_whitespace()).collect();
    compact.contains("200OK")
        && compact.contains("\"service\":\"stock-MINGCommandCenter3.0\"")
        && compact.contains("\"status\":\"ok\"")
        && compact.contains("\"external_calls_on_startup\":false")
        && compact.contains("\"external_calls_triggered\":false")
        && compact.contains("\"provider_or_model_calls\":false")
        && compact.contains("\"real_trading_enabled\":false")
}

fn spawn_local_fastapi(project_root: &Path) -> Result<u32, String> {
    let log_dir = project_root.join(".stock_ming_3/logs");
    fs::create_dir_all(&log_dir).map_err(|error| error.to_string())?;
    let log_path = log_dir.join("tauri_fastapi_autostart.log");
    let stdout = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|error| error.to_string())?;
    let stderr = stdout.try_clone().map_err(|error| error.to_string())?;

    let mut child = Command::new(python_executable(project_root))
        .current_dir(project_root)
        .args([
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            FASTAPI_HOST,
            "--port",
            &FASTAPI_PORT.to_string(),
        ])
        .env("PYTHONUNBUFFERED", "1")
        .env("STOCK_MING_FASTAPI_AUTOSTART", "tauri_app_open")
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|error| error.to_string())?;
    let pid = child.id();

    thread::spawn(move || {
        let _ = child.wait();
    });

    Ok(pid)
}

fn append_autostart_log(project_root: &Path, message: &str) {
    let log_dir = project_root.join(".stock_ming_3/logs");
    if fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let log_path = log_dir.join("tauri_fastapi_autostart.log");
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(file, "[tauri-fastapi-autostart] {message}");
    }
}
