//! Private LTG-10 packaged-WebView QA adapter.
//!
//! This module has no command, port, invoke handler, environment switch, or
//! public report input.  It is enabled only when the recorder's child process
//! inherits two pipe descriptors and supplies both private CLI flags.  The
//! application validates the challenge, parent process, executable and nonce,
//! observes its own production WebView, takes native WKWebView snapshots, then
//! writes one length-framed response to the inherited output pipe.

use flate2::{write::GzEncoder, Compression, GzBuilder};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::{
    env,
    ffi::CStr,
    fs::{self, File},
    io::{Read, Write},
    os::fd::{FromRawFd, RawFd},
    os::unix::ffi::OsStrExt,
    path::{Path, PathBuf},
    sync::mpsc::{self, RecvTimeoutError},
    sync::OnceLock,
    thread,
    time::{Duration, Instant},
};
use tauri::{LogicalSize, Manager, WebviewWindow};

const INPUT_SCHEMA: &str = "streamlit_retirement_packaged_native_input.v1";
const OUTPUT_SCHEMA: &str = "streamlit_retirement_packaged_native_output.v2";
const APP_ATTESTATION_SCHEMA: &str = "streamlit_retirement_packaged_app_attestation.v7";
const CHALLENGE_SCHEMA: &str = "streamlit_retirement_packaged_runner_challenge.v6";
const MAX_INPUT_BYTES: usize = 256 * 1024;
const MAX_EVAL_BYTES: usize = 16 * 1024 * 1024;
const MAX_SNAPSHOT_BYTES: usize = 32 * 1024 * 1024;
const MAX_COMPRESSED_OUTPUT_JSON_BYTES: usize = 64 * 1024 * 1024;
const MAX_UNCOMPRESSED_OUTPUT_JSON_BYTES: usize = 192 * 1024 * 1024;
const OUTPUT_FRAME_MAGIC: &[u8; 8] = b"LTG10QA1";
const OUTPUT_FRAME_CODEC: u8 = 1;
const OUTPUT_FRAME_FLAGS: u8 = 0;
const OUTPUT_FRAME_RESERVED: [u8; 6] = [0; 6];
const OUTPUT_FRAME_CODEC_NAME: &str = "gzip_deterministic_v1";
const QA_IN_FLAG: &str = "--ltg10-qa-in-fd";
const QA_OUT_FLAG: &str = "--ltg10-qa-out-fd";
const FINAL_DENY_WINDOW_MS: u64 = 10_750;
const FINAL_NETWORK_GUARD: &str = "quiesce_tracked_intervals_then_deny_all_then_exit";
const VIEWPORT_RESIZE_ATTEMPTS: usize = 8;
const VIEWPORT_RESIZE_SETTLE_MS: u64 = 150;
const VIEWPORT_MAX_CORRECTION_CSS_PX: i64 = 256;

const ROUTES: [(&str, &str, &str); 6] = [
    ("#home", "CommandCenterHome", "今日作战台"),
    ("#candidates", "CandidateRadar", "下一票雷达"),
    ("#factor", "FactorQuantHub", "股票量化推演"),
    ("#next", "NextSessionMap", "次日图谱"),
    ("#marginEtf", "MarginEtf", "ETF / 融资"),
    ("#qmt-replay", "QmtReplayLab", "QMT 本地回放"),
];
const VIEWPORTS: [(&str, u32, u32); 2] = [("desktop", 1440, 820), ("mobile", 390, 844)];

/// Installed at document-start only for an authenticated inherited-FD session.
pub const INITIALIZATION_SCRIPT: &str = include_str!("ltg10_packaged_qa_init.js");

#[derive(Debug)]
pub struct TrustedSession {
    input_fd: RawFd,
    output_fd: RawFd,
}

#[derive(Clone, Copy, Debug)]
struct NativeWebviewContent {
    origin_x: f64,
    origin_y: f64,
    width_points: f64,
    height_points: f64,
    width_pixels: u32,
    height_pixels: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum EvalError {
    Dispatch,
    CallbackTimeout,
    CallbackDisconnected,
    ResultTooLarge,
    ResultInvalid,
}

impl EvalError {
    fn safe_message(self) -> &'static str {
        match self {
            Self::Dispatch => "WebView eval dispatch failed",
            Self::CallbackTimeout => "WebView eval callback timed out",
            Self::CallbackDisconnected => "WebView eval callback disconnected",
            Self::ResultTooLarge => "WebView eval result exceeds private limit",
            Self::ResultInvalid => "WebView eval result invalid",
        }
    }
}

impl From<EvalError> for String {
    fn from(error: EvalError) -> Self {
        error.safe_message().into()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum StartupEvalDecision {
    Ready,
    Retry,
    Fail(EvalError),
}

fn startup_eval_decision(
    result: Result<Value, EvalError>,
    before_deadline: bool,
) -> StartupEvalDecision {
    if !before_deadline {
        return StartupEvalDecision::Fail(EvalError::CallbackTimeout);
    }
    match result {
        Ok(Value::Bool(true)) => StartupEvalDecision::Ready,
        Ok(_) | Err(EvalError::CallbackDisconnected) => StartupEvalDecision::Retry,
        Err(error) => StartupEvalDecision::Fail(error),
    }
}

fn startup_attempt_deadline(now: Instant, global_deadline: Instant) -> Option<Instant> {
    if now >= global_deadline {
        return None;
    }
    Some(
        now.checked_add(Duration::from_secs(20))
            .unwrap_or(global_deadline)
            .min(global_deadline),
    )
}

fn eval_deadline_budget(now: Instant, deadline: Instant) -> Result<Duration, EvalError> {
    let remaining = deadline.saturating_duration_since(now);
    if remaining.is_zero() {
        Err(EvalError::CallbackTimeout)
    } else {
        Ok(remaining)
    }
}

fn fixed_path_is_direct(project_root: &Path, path: &Path, directory: bool) -> bool {
    let Ok(relative) = path.strip_prefix(project_root) else {
        return false;
    };
    let Ok(root_metadata) = fs::symlink_metadata(project_root) else {
        return false;
    };
    if root_metadata.file_type().is_symlink() || !root_metadata.is_dir() {
        return false;
    }
    let mut cursor = project_root.to_path_buf();
    for part in relative.components() {
        cursor.push(part.as_os_str());
        let Ok(metadata) = fs::symlink_metadata(&cursor) else {
            return false;
        };
        if metadata.file_type().is_symlink() {
            return false;
        }
    }
    fs::symlink_metadata(path).is_ok_and(|metadata| {
        !metadata.file_type().is_symlink()
            && if directory {
                metadata.is_dir()
            } else {
                metadata.is_file()
            }
    })
}

fn bundle_fingerprint(bundle: &Path) -> Result<String, String> {
    fn collect(directory: &Path, paths: &mut Vec<PathBuf>) -> Result<(), String> {
        let entries = fs::read_dir(directory).map_err(|_| "bundle directory read failed")?;
        for entry in entries {
            let path = entry
                .map_err(|_| "bundle directory entry read failed")?
                .path();
            let metadata =
                fs::symlink_metadata(&path).map_err(|_| "bundle entry metadata failed")?;
            paths.push(path.clone());
            if metadata.is_dir() && !metadata.file_type().is_symlink() {
                collect(&path, paths)?;
            }
        }
        Ok(())
    }

    let mut paths = Vec::new();
    collect(bundle, &mut paths)?;
    paths.sort_by(|left, right| {
        left.strip_prefix(bundle)
            .unwrap_or(left)
            .as_os_str()
            .as_bytes()
            .cmp(
                right
                    .strip_prefix(bundle)
                    .unwrap_or(right)
                    .as_os_str()
                    .as_bytes(),
            )
    });
    let mut hasher = Sha256::new();
    let mut file_count = 0_u64;
    for path in paths {
        let relative = path
            .strip_prefix(bundle)
            .map_err(|_| "bundle entry escaped root")?;
        let relative_text = relative
            .to_str()
            .ok_or("bundle entry path not UTF-8")?
            .replace(std::path::MAIN_SEPARATOR, "/");
        let relative_bytes = relative_text.as_bytes();
        let length =
            u32::try_from(relative_bytes.len()).map_err(|_| "bundle entry path too long")?;
        hasher.update(length.to_be_bytes());
        hasher.update(relative_bytes);
        let metadata = fs::symlink_metadata(&path).map_err(|_| "bundle entry metadata failed")?;
        if metadata.file_type().is_symlink() {
            hasher.update(b"L");
            let target = fs::read_link(&path).map_err(|_| "bundle symlink read failed")?;
            hasher.update(target.as_os_str().as_bytes());
        } else if !metadata.is_file() {
            hasher.update(b"D");
        } else {
            hasher.update(b"F");
            let mut file = File::open(&path).map_err(|_| "bundle file open failed")?;
            let mut buffer = [0_u8; 1024 * 1024];
            loop {
                let count = file
                    .read(&mut buffer)
                    .map_err(|_| "bundle file hash read failed")?;
                if count == 0 {
                    break;
                }
                hasher.update(&buffer[..count]);
            }
            file_count += 1;
        }
    }
    Ok(if file_count > 0 {
        format!("{:x}", hasher.finalize())
    } else {
        String::new()
    })
}

fn measure_package_identity(
    executable: &Path,
    bundle: &Path,
    dmg: &Path,
    bundle_identifier: &str,
    bundle_version: &str,
) -> Result<PackageIdentity, String> {
    let project_root = bundle
        .ancestors()
        .nth(7)
        .ok_or("fixed packaged bundle is not under project root")?;
    let expected_bundle = project_root
        .join("desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app");
    let expected_dmg = project_root.join(
        "desktop/src-tauri/target/release/bundle/dmg/stock-MING Command Center_3.0.0_aarch64.dmg",
    );
    let expected_executable = expected_bundle.join("Contents/MacOS/stock_ming_command_center");
    if bundle != expected_bundle
        || dmg != expected_dmg
        || executable != expected_executable
        || !fixed_path_is_direct(project_root, bundle, true)
        || !fixed_path_is_direct(project_root, dmg, false)
        || !fixed_path_is_direct(project_root, executable, false)
    {
        return Err("fixed packaged artifact path invalid".into());
    }
    let executable_sha256 = sha256_file(executable)?;
    let bundle_sha256 = bundle_fingerprint(bundle)?;
    let dmg_sha256 = sha256_file(dmg)?;
    let artifact_set_sha256 = sha256_hex(
        format!("{bundle_sha256}|{dmg_sha256}|{bundle_identifier}|{bundle_version}").as_bytes(),
    );
    Ok(PackageIdentity {
        executable_path: executable.to_path_buf(),
        bundle_path: bundle.to_path_buf(),
        dmg_path: dmg.to_path_buf(),
        bundle_identifier: bundle_identifier.to_owned(),
        bundle_version: bundle_version.to_owned(),
        executable_sha256,
        bundle_sha256,
        dmg_sha256,
        artifact_set_sha256,
    })
}

#[derive(Debug)]
struct Input {
    challenge: Value,
    nonce: [u8; 32],
    runner_pid: u32,
    runner_executable_path: PathBuf,
}

#[derive(Debug)]
struct PackageIdentity {
    executable_path: PathBuf,
    bundle_path: PathBuf,
    dmg_path: PathBuf,
    bundle_identifier: String,
    bundle_version: String,
    executable_sha256: String,
    bundle_sha256: String,
    dmg_sha256: String,
    artifact_set_sha256: String,
}

impl TrustedSession {
    pub fn from_process_args() -> Result<Option<Self>, String> {
        let args: Vec<String> = env::args().collect();
        let mentions_qa = args.iter().any(|arg| {
            arg == QA_IN_FLAG
                || arg == QA_OUT_FLAG
                || arg.starts_with(&format!("{QA_IN_FLAG}="))
                || arg.starts_with(&format!("{QA_OUT_FLAG}="))
        });
        if !mentions_qa {
            return Ok(None);
        }
        let input_fd = exact_fd_arg(&args, QA_IN_FLAG)?;
        let output_fd = exact_fd_arg(&args, QA_OUT_FLAG)?;
        if input_fd == output_fd || input_fd < 3 || output_fd < 3 {
            return Err("qa descriptors must be distinct inherited descriptors >= 3".into());
        }
        validate_pipe_fd(input_fd, libc::O_RDONLY)?;
        validate_pipe_fd(output_fd, libc::O_WRONLY)?;
        Ok(Some(Self {
            input_fd,
            output_fd,
        }))
    }
}

fn exact_fd_arg(args: &[String], flag: &str) -> Result<RawFd, String> {
    let indexes: Vec<usize> = args
        .iter()
        .enumerate()
        .filter_map(|(index, value)| (value == flag).then_some(index))
        .collect();
    if indexes.len() != 1 || indexes[0] + 1 >= args.len() {
        return Err(format!("{flag} must occur exactly once with a descriptor"));
    }
    let value = &args[indexes[0] + 1];
    if value.starts_with('-') || args.iter().any(|arg| arg.starts_with(&format!("{flag}="))) {
        return Err(format!("{flag} descriptor syntax is invalid"));
    }
    value
        .parse::<RawFd>()
        .map_err(|_| format!("{flag} descriptor is invalid"))
}

fn validate_pipe_fd(fd: RawFd, expected_access: i32) -> Result<(), String> {
    let mut metadata = std::mem::MaybeUninit::<libc::stat>::uninit();
    // SAFETY: metadata points to writable stat storage and fd is caller-supplied.
    if unsafe { libc::fstat(fd, metadata.as_mut_ptr()) } != 0 {
        return Err("qa inherited descriptor is not open".into());
    }
    // SAFETY: fstat succeeded.
    let metadata = unsafe { metadata.assume_init() };
    if metadata.st_mode & libc::S_IFMT != libc::S_IFIFO {
        return Err("qa inherited descriptor is not a pipe".into());
    }
    // SAFETY: F_GETFL does not mutate memory.
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
    if flags < 0 || flags & libc::O_ACCMODE != expected_access {
        return Err("qa inherited descriptor access mode is invalid".into());
    }
    Ok(())
}

pub fn start<R: tauri::Runtime>(
    app: &mut tauri::App<R>,
    session: TrustedSession,
) -> Result<(), Box<dyn std::error::Error>> {
    let window = app
        .get_webview_window("main")
        .ok_or("main packaged webview missing")?;
    let handle = app.handle().clone();
    thread::spawn(move || {
        let code = match run(window, session) {
            Ok(()) => 0,
            Err(error) => {
                eprintln!("ltg10 packaged QA failed closed: {error}");
                78
            }
        };
        handle.exit(code);
    });
    Ok(())
}

fn run<R: tauri::Runtime>(window: WebviewWindow<R>, session: TrustedSession) -> Result<(), String> {
    let input = read_input(session.input_fd)?;
    let initial_package_identity = validate_input(&input)?;
    wait_for_document(&window)?;
    let mut rows = Vec::with_capacity(12);
    let mut screenshots = Vec::with_capacity(12);
    for (viewport, width, height) in VIEWPORTS {
        converge_webview_content_size(&window, width, height)?;
        for (route, component, expected_heading) in ROUTES {
            navigate(&window, route)?;
            let started = monotonic_ns();
            let observation = observe(
                &window,
                route,
                component,
                expected_heading,
                viewport,
                width,
                height,
            )?;
            let observed_inner_width = observation
                .get("observed_inner_width")
                .and_then(Value::as_u64)
                .ok_or("WebView inner width measurement missing")?;
            let observed_inner_height = observation
                .get("observed_inner_height")
                .and_then(Value::as_u64)
                .ok_or("WebView inner height measurement missing")?;
            let device_pixel_ratio = observation
                .get("device_pixel_ratio")
                .and_then(Value::as_f64)
                .filter(|value| value.is_finite() && *value >= 1.0 && *value <= 4.0)
                .ok_or("WebView devicePixelRatio measurement invalid")?;
            if observed_inner_width != u64::from(width)
                || observed_inner_height != u64::from(height)
            {
                return Err(
                    "WebView actual inner viewport does not match requested content size".into(),
                );
            }
            let expected_physical_width = (f64::from(width) * device_pixel_ratio).round() as u32;
            let expected_physical_height = (f64::from(height) * device_pixel_ratio).round() as u32;
            let native_content =
                native_webview_content(&window, width, height, device_pixel_ratio)?;
            if native_content.width_pixels != expected_physical_width
                || native_content.height_pixels != expected_physical_height
            {
                return Err("native WebView content size is not bound to measured DPR".into());
            }
            let snapshot = native_snapshot(&window, &native_content)?;
            if snapshot.len() > MAX_SNAPSHOT_BYTES {
                return Err("native snapshot exceeds private frame limit".into());
            }
            let finished = monotonic_ns();
            let screenshot_sha256 = sha256_hex(&snapshot);
            let (screenshot_pixel_width, screenshot_pixel_height) = png_dimensions(&snapshot)?;
            if screenshot_pixel_width != native_content.width_pixels
                || screenshot_pixel_height != native_content.height_pixels
            {
                return Err(
                    "native snapshot pixels do not match measured native inner size".into(),
                );
            }
            let mut row = observation
                .as_object()
                .cloned()
                .ok_or("packaged DOM observation is not an object")?;
            row.insert("route".into(), Value::String(route.into()));
            row.insert("component".into(), Value::String(component.into()));
            row.insert("viewport".into(), Value::String(viewport.into()));
            row.insert("width".into(), Value::from(width));
            row.insert("height".into(), Value::from(height));
            row.insert(
                "native_inner_width_px".into(),
                Value::from(native_content.width_pixels),
            );
            row.insert(
                "native_inner_height_px".into(),
                Value::from(native_content.height_pixels),
            );
            row.insert(
                "screenshot_pixel_width".into(),
                Value::from(screenshot_pixel_width),
            );
            row.insert(
                "screenshot_pixel_height".into(),
                Value::from(screenshot_pixel_height),
            );
            row.insert(
                "runtime_surface".into(),
                Value::String("actual_packaged_tauri_react".into()),
            );
            row.insert("protocol".into(), Value::String("tauri:".into()));
            row.insert(
                "observation_started_monotonic_ns".into(),
                Value::from(started),
            );
            row.insert(
                "observation_finished_monotonic_ns".into(),
                Value::from(finished),
            );
            row.insert("screenshot_index".into(), Value::from(rows.len()));
            row.insert("screenshot_byte_length".into(), Value::from(snapshot.len()));
            row.insert("screenshot_sha256".into(), Value::String(screenshot_sha256));
            row.insert("screenshot_native_snapshot".into(), Value::Bool(true));
            rows.push(Value::Object(row));
            screenshots.push(snapshot);
        }
    }
    let seal_audit = seal_audit(&window)?;
    if rows.last().and_then(|row| row.get("network_ledger"))
        != seal_audit.get("ledger_digest_material")
    {
        return Err("network activity occurred after the final route observation".into());
    }
    let route_payload_sha256 = digest(&Value::Array(rows.clone()));
    let challenge = input
        .challenge
        .as_object()
        .ok_or("challenge object missing")?;
    let executable =
        env::current_exe().map_err(|error| format!("current executable unavailable: {error}"))?;
    let exit_contract = json!({
        "final_network_guard": FINAL_NETWORK_GUARD,
        "final_window_ms": seal_audit.get("final_window_ms").cloned().unwrap_or(Value::Null),
        "exit_after_output": true,
        "expected_exit_code": 0,
    });
    let package_identity = measure_package_identity(
        &initial_package_identity.executable_path,
        &initial_package_identity.bundle_path,
        &initial_package_identity.dmg_path,
        &initial_package_identity.bundle_identifier,
        &initial_package_identity.bundle_version,
    )?;
    if package_identity.executable_sha256 != initial_package_identity.executable_sha256
        || package_identity.bundle_sha256 != initial_package_identity.bundle_sha256
        || package_identity.dmg_sha256 != initial_package_identity.dmg_sha256
        || package_identity.artifact_set_sha256 != initial_package_identity.artifact_set_sha256
    {
        return Err("fixed packaged artifact identity changed during QA".into());
    }
    let mut app_attestation = json!({
        "schema_version": APP_ATTESTATION_SCHEMA,
        "status": "packaged_tauri_app_nonce_attested",
        "pid": std::process::id(),
        "parent_pid": input.runner_pid,
        "parent_executable_path": input.runner_executable_path,
        "executable_path": executable,
        "executable_sha256": package_identity.executable_sha256,
        "bundle_sha256": package_identity.bundle_sha256,
        "artifact_set_sha256": package_identity.artifact_set_sha256,
        "dmg_sha256": package_identity.dmg_sha256,
        "head_full": challenge.get("head_full").cloned().unwrap_or(Value::Null),
        "challenge_digest": challenge.get("challenge_digest").cloned().unwrap_or(Value::Null),
        "nonce_digest": sha256_hex(&input.nonce),
        "source_contract_digest": challenge.get("source_contract_digest").cloned().unwrap_or(Value::Null),
        "ordinary_component_map_digest": challenge.get("ordinary_component_map_digest").cloned().unwrap_or(Value::Null),
        "route_payload_sha256": route_payload_sha256,
        "network_seal_sha256": digest(&seal_audit),
        "native_snapshot_api": "WKWebView.takeSnapshotWithConfiguration.afterScreenUpdates",
        "final_network_guard": FINAL_NETWORK_GUARD,
        "final_window_ms": seal_audit.get("final_window_ms").cloned().unwrap_or(Value::Null),
        "exit_after_output": true,
        "expected_exit_code": 0,
        "exit_contract_sha256": digest(&exit_contract),
    });
    add_nonce_response(&mut app_attestation, &input.nonce, "response_sha256")?;
    let output = json!({
        "schema_version": OUTPUT_SCHEMA,
        "status": "actual_packaged_tauri_native_matrix_captured",
        "app_attestation": app_attestation,
        "route_count": ROUTES.len(),
        "viewport_count": VIEWPORTS.len(),
        "qa_matrix_count": rows.len(),
        "rows": rows,
        "seal_audit": seal_audit,
        "external_calls_triggered": false,
        "tushare_called": false,
        "deepseek_called": false,
        "github_called": false,
        "does_not_execute_trades": true,
        "does_not_modify_strategy_action": true,
        "contains_secret": false,
    });
    write_output(session.output_fd, &output, &screenshots, &input.nonce)
}

fn converge_webview_content_size<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    target_width: u32,
    target_height: u32,
) -> Result<(), String> {
    let mut requested_width = f64::from(target_width);
    let mut requested_height = f64::from(target_height);
    for _attempt in 0..VIEWPORT_RESIZE_ATTEMPTS {
        window
            .set_size(LogicalSize::new(requested_width, requested_height))
            .map_err(|error| format!("native viewport resize failed: {error}"))?;
        thread::sleep(Duration::from_millis(VIEWPORT_RESIZE_SETTLE_MS));
        let observed = eval(
            window,
            "({width: window.innerWidth, height: window.innerHeight})",
        )?;
        let observed_width = observed
            .get("width")
            .and_then(Value::as_u64)
            .and_then(|value| u32::try_from(value).ok())
            .ok_or("native viewport resize observation invalid")?;
        let observed_height = observed
            .get("height")
            .and_then(Value::as_u64)
            .and_then(|value| u32::try_from(value).ok())
            .ok_or("native viewport resize observation invalid")?;
        if observed_width == target_width && observed_height == target_height {
            return Ok(());
        }
        let width_correction = i64::from(target_width) - i64::from(observed_width);
        let height_correction = i64::from(target_height) - i64::from(observed_height);
        if width_correction.abs() > VIEWPORT_MAX_CORRECTION_CSS_PX
            || height_correction.abs() > VIEWPORT_MAX_CORRECTION_CSS_PX
        {
            continue;
        }
        requested_width += width_correction as f64;
        requested_height += height_correction as f64;
        if !requested_width.is_finite()
            || !requested_height.is_finite()
            || requested_width <= 0.0
            || requested_height <= 0.0
            || (requested_width - f64::from(target_width)).abs()
                > VIEWPORT_MAX_CORRECTION_CSS_PX as f64
            || (requested_height - f64::from(target_height)).abs()
                > VIEWPORT_MAX_CORRECTION_CSS_PX as f64
        {
            return Err("native viewport resize correction invalid".into());
        }
    }
    Err("native viewport resize did not converge".into())
}

#[cfg(target_os = "macos")]
fn native_webview_content<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    expected_width: u32,
    expected_height: u32,
    device_pixel_ratio: f64,
) -> Result<NativeWebviewContent, String> {
    use objc2_web_kit::WKWebView;

    let (sender, receiver) = mpsc::sync_channel(1);
    window
        .with_webview(move |platform| unsafe {
            let view: &WKWebView = &*platform.inner().cast();
            let bounds = view.bounds();
            let insets = view.safeAreaInsets();
            let _ = sender.send((
                bounds.origin.x,
                bounds.origin.y,
                bounds.size.width,
                bounds.size.height,
                insets.top,
                insets.right,
                insets.bottom,
                insets.left,
                view.isFlipped(),
            ));
        })
        .map_err(|error| format!("WKWebView content geometry dispatch failed: {error}"))?;
    let (bounds_x, bounds_y, bounds_width, bounds_height, top, right, bottom, left, flipped) =
        receiver
            .recv_timeout(Duration::from_secs(20))
            .map_err(|_| "WKWebView content geometry timed out".to_string())?;
    let geometry_values = [
        bounds_x,
        bounds_y,
        bounds_width,
        bounds_height,
        top,
        right,
        bottom,
        left,
    ];
    if geometry_values.iter().any(|value| !value.is_finite())
        || bounds_width <= 0.0
        || bounds_height <= 0.0
        || [top, right, bottom, left].iter().any(|value| *value < 0.0)
    {
        return Err("WKWebView safe-area geometry invalid".into());
    }
    let width_points = bounds_width - left - right;
    let height_points = bounds_height - top - bottom;
    if width_points != f64::from(expected_width) || height_points != f64::from(expected_height) {
        return Err("WKWebView safe-area content does not match DOM viewport".into());
    }
    let native_scale = window
        .scale_factor()
        .map_err(|error| format!("native scale-factor measurement failed: {error}"))?;
    if !native_scale.is_finite()
        || native_scale < 1.0
        || native_scale > 4.0
        || native_scale != device_pixel_ratio
    {
        return Err("WKWebView native scale is not bound to measured DPR".into());
    }
    let scaled_width = width_points * native_scale;
    let scaled_height = height_points * native_scale;
    if !scaled_width.is_finite()
        || !scaled_height.is_finite()
        || scaled_width != scaled_width.round()
        || scaled_height != scaled_height.round()
        || scaled_width <= 0.0
        || scaled_height <= 0.0
        || scaled_width > f64::from(u32::MAX)
        || scaled_height > f64::from(u32::MAX)
    {
        return Err("WKWebView native pixel geometry invalid".into());
    }
    Ok(NativeWebviewContent {
        origin_x: bounds_x + left,
        origin_y: bounds_y + if flipped { top } else { bottom },
        width_points,
        height_points,
        width_pixels: scaled_width as u32,
        height_pixels: scaled_height as u32,
    })
}

#[cfg(not(target_os = "macos"))]
fn native_webview_content<R: tauri::Runtime>(
    _window: &WebviewWindow<R>,
    _expected_width: u32,
    _expected_height: u32,
    _device_pixel_ratio: f64,
) -> Result<NativeWebviewContent, String> {
    Err("WKWebView content geometry unavailable on this platform".into())
}

fn read_input(fd: RawFd) -> Result<Input, String> {
    // SAFETY: ownership of the inherited one-shot descriptor transfers here.
    let mut file = unsafe { File::from_raw_fd(fd) };
    let mut length = [0_u8; 8];
    file.read_exact(&mut length)
        .map_err(|_| "native input frame missing".to_string())?;
    let length = u64::from_be_bytes(length) as usize;
    if length == 0 || length > MAX_INPUT_BYTES {
        return Err("native input frame length invalid".into());
    }
    let mut data = vec![0_u8; length];
    file.read_exact(&mut data)
        .map_err(|_| "native input frame truncated".to_string())?;
    let mut nonce = [0_u8; 32];
    file.read_exact(&mut nonce)
        .map_err(|_| "native nonce missing".to_string())?;
    let mut trailing = [0_u8; 1];
    if file
        .read(&mut trailing)
        .map_err(|_| "native input trailing read failed".to_string())?
        != 0
    {
        return Err("native input has trailing bytes".into());
    }
    let value: Value =
        serde_json::from_slice(&data).map_err(|_| "native input JSON invalid".to_string())?;
    let object = value.as_object().ok_or("native input must be object")?;
    let exact = [
        "schema_version",
        "challenge",
        "runner_pid",
        "runner_executable_path",
    ];
    if object.len() != exact.len() || exact.iter().any(|field| !object.contains_key(*field)) {
        return Err("native input fields invalid".into());
    }
    if object.get("schema_version").and_then(Value::as_str) != Some(INPUT_SCHEMA) {
        return Err("native input schema invalid".into());
    }
    let runner_pid = object
        .get("runner_pid")
        .and_then(Value::as_u64)
        .ok_or("runner pid invalid")? as u32;
    let runner_path = object
        .get("runner_executable_path")
        .and_then(Value::as_str)
        .map(PathBuf::from)
        .ok_or("runner executable path invalid")?;
    Ok(Input {
        challenge: object.get("challenge").cloned().unwrap_or(Value::Null),
        nonce,
        runner_pid,
        runner_executable_path: runner_path,
    })
}

fn validate_input(input: &Input) -> Result<PackageIdentity, String> {
    let object = input
        .challenge
        .as_object()
        .ok_or("challenge must be object")?;
    const FIELDS: [&str; 24] = [
        "schema_version",
        "challenge_id",
        "nonce_digest",
        "created_at_utc",
        "head_full",
        "runner_source_sha256",
        "source_contract_digest",
        "ordinary_component_map_digest",
        "package_head_full",
        "artifact_set_sha256",
        "app_bundle_sha256",
        "app_executable_sha256",
        "dmg_sha256",
        "app_executable_path",
        "app_bundle_path",
        "dmg_path",
        "bundle_identifier",
        "bundle_version",
        "expected_routes",
        "expected_viewports",
        "production_required",
        "browser_or_vite_substitute_allowed",
        "external_calls_allowed",
        "challenge_digest",
    ];
    if object.get("schema_version").and_then(Value::as_str) != Some(CHALLENGE_SCHEMA)
        || object.len() != FIELDS.len()
        || FIELDS.iter().any(|field| !object.contains_key(*field))
    {
        return Err("challenge schema invalid".into());
    }
    let mut material = object.clone();
    let observed_digest = material
        .remove("challenge_digest")
        .and_then(|value| value.as_str().map(str::to_owned))
        .ok_or("challenge digest missing")?;
    if digest(&Value::Object(material)) != observed_digest {
        return Err("challenge digest invalid".into());
    }
    if object.get("nonce_digest").and_then(Value::as_str) != Some(&sha256_hex(&input.nonce)) {
        return Err("challenge nonce mismatch".into());
    }
    if object.get("production_required") != Some(&Value::Bool(true))
        || object.get("browser_or_vite_substitute_allowed") != Some(&Value::Bool(false))
        || object.get("external_calls_allowed") != Some(&Value::Bool(false))
        || object.get("head_full") != object.get("package_head_full")
    {
        return Err("challenge production boundary invalid".into());
    }
    let expected_routes = Value::Array(
        ROUTES
            .iter()
            .map(|(route, _, _)| Value::String((*route).into()))
            .collect(),
    );
    let expected_viewports = json!({
        "desktop": {"width": 1440, "height": 820},
        "mobile": {"width": 390, "height": 844},
    });
    if object.get("expected_routes") != Some(&expected_routes)
        || object.get("expected_viewports") != Some(&expected_viewports)
        || !object
            .get("head_full")
            .and_then(Value::as_str)
            .is_some_and(valid_git_head)
        || ![
            "runner_source_sha256",
            "source_contract_digest",
            "ordinary_component_map_digest",
            "artifact_set_sha256",
            "app_bundle_sha256",
            "app_executable_sha256",
            "dmg_sha256",
        ]
        .iter()
        .all(|field| {
            object
                .get(*field)
                .and_then(Value::as_str)
                .is_some_and(valid_hex_digest)
        })
    {
        return Err("challenge route, viewport, or digest contract invalid".into());
    }
    let parent_pid = unsafe { libc::getppid() } as u32;
    if parent_pid != input.runner_pid || parent_pid <= 1 {
        return Err("runner parent pid mismatch".into());
    }
    let observed_parent = process_path(parent_pid)?;
    if observed_parent != input.runner_executable_path || !observed_parent.is_absolute() {
        return Err("runner parent executable mismatch".into());
    }
    let executable = env::current_exe().map_err(|_| "app executable unavailable")?;
    let expected_executable = PathBuf::from(
        object
            .get("app_executable_path")
            .and_then(Value::as_str)
            .ok_or("expected app executable missing")?,
    );
    let expected_bundle = PathBuf::from(
        object
            .get("app_bundle_path")
            .and_then(Value::as_str)
            .ok_or("expected app bundle missing")?,
    );
    let expected_dmg = PathBuf::from(
        object
            .get("dmg_path")
            .and_then(Value::as_str)
            .ok_or("expected packaged DMG missing")?,
    );
    let bundle_identifier = object
        .get("bundle_identifier")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or("expected bundle identifier missing")?;
    let bundle_version = object
        .get("bundle_version")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or("expected bundle version missing")?;
    let expected_bundle_executable = expected_bundle
        .join("Contents")
        .join("MacOS")
        .join("stock_ming_command_center");
    let identity = measure_package_identity(
        &expected_executable,
        &expected_bundle,
        &expected_dmg,
        bundle_identifier,
        bundle_version,
    )?;
    if executable != expected_executable
        || !expected_bundle.is_absolute()
        || expected_executable != expected_bundle_executable
        || identity.executable_sha256
            != object
                .get("app_executable_sha256")
                .and_then(Value::as_str)
                .unwrap_or("")
        || identity.bundle_sha256
            != object
                .get("app_bundle_sha256")
                .and_then(Value::as_str)
                .unwrap_or("")
        || identity.dmg_sha256
            != object
                .get("dmg_sha256")
                .and_then(Value::as_str)
                .unwrap_or("")
        || identity.artifact_set_sha256
            != object
                .get("artifact_set_sha256")
                .and_then(Value::as_str)
                .unwrap_or("")
    {
        return Err("packaged executable identity mismatch".into());
    }
    Ok(identity)
}

#[cfg(target_os = "macos")]
fn process_path(pid: u32) -> Result<PathBuf, String> {
    #[link(name = "proc")]
    extern "C" {
        fn proc_pidpath(
            pid: libc::c_int,
            buffer: *mut libc::c_void,
            buffersize: u32,
        ) -> libc::c_int;
    }
    let mut buffer = vec![0_u8; 4096];
    // SAFETY: proc_pidpath writes at most buffer.len() bytes to valid storage.
    let written =
        unsafe { proc_pidpath(pid as i32, buffer.as_mut_ptr().cast(), buffer.len() as u32) };
    if written <= 0 || written as usize >= buffer.len() {
        return Err("runner process path unavailable".into());
    }
    buffer[written as usize] = 0;
    let value = CStr::from_bytes_until_nul(&buffer)
        .map_err(|_| "runner process path invalid")?
        .to_str()
        .map_err(|_| "runner process path not UTF-8")?;
    Ok(PathBuf::from(value))
}

#[cfg(not(target_os = "macos"))]
fn process_path(_pid: u32) -> Result<PathBuf, String> {
    Err("native packaged QA is macOS-only".into())
}

fn wait_for_document<R: tauri::Runtime>(window: &WebviewWindow<R>) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        let Some(attempt_deadline) = startup_attempt_deadline(Instant::now(), deadline) else {
            break;
        };
        let result = eval_with_deadline(
            window,
            "Boolean(window.__STOCK_MING_LTG10_QA__ && document.querySelector('#root'))",
            attempt_deadline,
        );
        match startup_eval_decision(result, Instant::now() < deadline) {
            StartupEvalDecision::Ready => return Ok(()),
            StartupEvalDecision::Retry => {}
            StartupEvalDecision::Fail(error) => return Err(error.into()),
        }
        thread::sleep(
            Duration::from_millis(200).min(deadline.saturating_duration_since(Instant::now())),
        );
    }
    Err("packaged QA document-start instrumentation unavailable".into())
}

fn navigate<R: tauri::Runtime>(window: &WebviewWindow<R>, route: &str) -> Result<(), String> {
    let route_key = route.trim_start_matches('#');
    let script = format!(
        r#"(() => {{
            const routeKey = {};
            const button = Array.from(document.querySelectorAll("button[data-route-key]")).find(
                (candidate) => candidate.getAttribute("data-route-key") === routeKey
            );
            if (!button) return false;
            button.click();
            const resetScroll = () => {{
                window.scrollTo(0, 0);
                if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
            }};
            resetScroll();
            queueMicrotask(resetScroll);
            requestAnimationFrame(resetScroll);
            return true;
        }})()"#,
        serde_json::to_string(route_key).map_err(|_| "route serialization failed")?
    );
    if eval(window, &script)? != Value::Bool(true) {
        return Err("packaged route navigation callback invalid".into());
    }
    Ok(())
}

fn observe<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    route: &str,
    component: &str,
    expected_heading: &str,
    viewport: &str,
    width: u32,
    height: u32,
) -> Result<Value, String> {
    let arguments = json!({
        "route": route,
        "component": component,
        "expected_heading": expected_heading,
        "viewport": viewport,
        "width": width,
        "height": height,
    });
    let script = format!(
        "window.__STOCK_MING_LTG10_QA__.beginObservation({})",
        serde_json::to_string(&arguments).map_err(|_| "observation arguments invalid")?
    );
    let token = eval(window, &script)?
        .as_str()
        .map(str::to_owned)
        .ok_or("observation token invalid")?;
    await_observation(window, &token, Duration::from_secs(25))
}

fn await_observation<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    token: &str,
    timeout: Duration,
) -> Result<Value, String> {
    let deadline = Instant::now() + timeout;
    let token_json =
        serde_json::to_string(token).map_err(|_| "observation token serialization failed")?;
    while Instant::now() < deadline {
        let state = eval(
            window,
            &format!("window.__STOCK_MING_LTG10_QA__.takeObservation({token_json})"),
        )?;
        match state.get("status").and_then(Value::as_str) {
            Some("pending") => thread::sleep(Duration::from_millis(50)),
            Some("ready") => {
                return state
                    .get("value")
                    .cloned()
                    .ok_or_else(|| "observation value missing".to_string())
            }
            Some("failed") => {
                return Err(format!(
                    "packaged WebView observation failed: {}",
                    state
                        .get("error")
                        .and_then(Value::as_str)
                        .unwrap_or("unknown")
                ))
            }
            _ => return Err("packaged WebView observation token state invalid".into()),
        }
    }
    Err("packaged WebView observation quiet wait timed out".into())
}

fn seal_audit<R: tauri::Runtime>(window: &WebviewWindow<R>) -> Result<Value, String> {
    let token = eval(window, "window.__STOCK_MING_LTG10_QA__.beginSeal()")?
        .as_str()
        .map(str::to_owned)
        .ok_or("seal token invalid")?;
    let started = await_observation(window, &token, Duration::from_secs(25))?;
    thread::sleep(Duration::from_millis(FINAL_DENY_WINDOW_MS + 100));
    let verified = eval(window, "window.__STOCK_MING_LTG10_QA__.verifySeal()")?;
    let started_count = started
        .get("ledger_count")
        .and_then(Value::as_u64)
        .ok_or("seal-start ledger count invalid")?;
    let quiesce_started = verified
        .get("quiesce_started_at_monotonic_ns")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let quiesce_completed = verified
        .get("quiesce_completed_at_monotonic_ns")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let interval_registration_count = verified
        .get("interval_registration_count")
        .and_then(Value::as_u64);
    let interval_clear_count = verified.get("interval_clear_count").and_then(Value::as_u64);
    let tracked_interval_count = verified
        .get("tracked_interval_count")
        .and_then(Value::as_u64);
    let quiesced_interval_count = verified
        .get("quiesced_interval_count")
        .and_then(Value::as_u64);
    let interval_quiescence_ready = verified.get("guard_mode").and_then(Value::as_str)
        == Some(FINAL_NETWORK_GUARD)
        && interval_registration_count.is_some()
        && interval_registration_count == interval_clear_count
        && tracked_interval_count.is_some()
        && tracked_interval_count == quiesced_interval_count
        && verified
            .get("active_interval_count_after_quiesce")
            .and_then(Value::as_u64)
            == Some(0)
        && verified.get("interval_registry_integrity") == Some(&Value::Bool(true))
        && quiesce_started > 0
        && quiesce_completed >= quiesce_started
        && verified.get("quiesce_complete") == Some(&Value::Bool(true))
        && verified
            .get("denied_interval_registration_count")
            .and_then(Value::as_u64)
            == Some(0);
    if verified.get("sealed") != Some(&Value::Bool(true))
        || verified
            .get("pending_request_count")
            .and_then(Value::as_u64)
            != Some(0)
        || verified.get("instrumentation_integrity") != Some(&Value::Bool(true))
        || verified.get("late_event_count").and_then(Value::as_u64) != Some(0)
        || verified.get("deny_all_network_guard") != Some(&Value::Bool(true))
        || verified.get("denied_attempt_count").and_then(Value::as_u64) != Some(0)
        || verified.get("final_window_ms").and_then(Value::as_u64) != Some(FINAL_DENY_WINDOW_MS)
        || verified
            .get("final_window_elapsed_ms")
            .and_then(Value::as_f64)
            .map_or(true, |elapsed| elapsed < FINAL_DENY_WINDOW_MS as f64)
        || verified.get("ledger_count").and_then(Value::as_u64) != Some(started_count)
        || !interval_quiescence_ready
    {
        return Err("final global quiet seal detected late or incomplete activity".into());
    }
    Ok(verified)
}

fn eval<R: tauri::Runtime>(window: &WebviewWindow<R>, script: &str) -> Result<Value, String> {
    eval_with_timeout(window, script, Duration::from_secs(20)).map_err(Into::into)
}

fn eval_with_timeout<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    script: &str,
    timeout: Duration,
) -> Result<Value, EvalError> {
    let deadline = Instant::now()
        .checked_add(timeout)
        .ok_or(EvalError::CallbackTimeout)?;
    eval_with_deadline(window, script, deadline)
}

fn eval_with_deadline<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    script: &str,
    deadline: Instant,
) -> Result<Value, EvalError> {
    let (sender, receiver) = mpsc::sync_channel(1);
    window
        .eval_with_callback(script, move |value| {
            let _ = sender.send(value);
        })
        .map_err(|_| EvalError::Dispatch)?;
    let receive_budget = eval_deadline_budget(Instant::now(), deadline)?;
    let raw = match receiver.recv_timeout(receive_budget) {
        Ok(value) => value,
        Err(RecvTimeoutError::Timeout) => return Err(EvalError::CallbackTimeout),
        Err(RecvTimeoutError::Disconnected) => return Err(EvalError::CallbackDisconnected),
    };
    eval_deadline_budget(Instant::now(), deadline)?;
    if raw.len() > MAX_EVAL_BYTES {
        return Err(EvalError::ResultTooLarge);
    }
    let mut value: Value = serde_json::from_str(&raw).map_err(|_| EvalError::ResultInvalid)?;
    if let Value::String(inner) = &value {
        if let Ok(decoded) = serde_json::from_str(inner) {
            value = decoded;
        }
    }
    eval_deadline_budget(Instant::now(), deadline)?;
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::{
        eval_deadline_budget, startup_attempt_deadline, startup_eval_decision, EvalError,
        StartupEvalDecision,
    };
    use serde_json::Value;
    use std::time::{Duration, Instant};

    #[test]
    fn startup_eval_retries_only_not_ready_or_disconnected() {
        assert_eq!(
            startup_eval_decision(Ok(Value::Bool(true)), true),
            StartupEvalDecision::Ready
        );
        assert_eq!(
            startup_eval_decision(Ok(Value::Bool(false)), true),
            StartupEvalDecision::Retry
        );
        assert_eq!(
            startup_eval_decision(Err(EvalError::CallbackDisconnected), true),
            StartupEvalDecision::Retry
        );
        assert_eq!(
            startup_eval_decision(Err(EvalError::CallbackTimeout), true),
            StartupEvalDecision::Fail(EvalError::CallbackTimeout)
        );
        assert_eq!(
            startup_eval_decision(Err(EvalError::Dispatch), true),
            StartupEvalDecision::Fail(EvalError::Dispatch)
        );
        assert_eq!(
            startup_eval_decision(Ok(Value::Bool(true)), false),
            StartupEvalDecision::Fail(EvalError::CallbackTimeout)
        );
    }

    #[test]
    fn startup_attempt_deadline_never_exceeds_global_budget() {
        let now = Instant::now();
        assert_eq!(
            startup_attempt_deadline(now, now + Duration::from_secs(30)),
            Some(now + Duration::from_secs(20))
        );
        assert_eq!(
            startup_attempt_deadline(now, now + Duration::from_millis(375)),
            Some(now + Duration::from_millis(375))
        );
        assert_eq!(startup_attempt_deadline(now, now), None);
        assert_eq!(
            startup_attempt_deadline(now + Duration::from_secs(10), now),
            None
        );

        let deadline = now + Duration::from_millis(375);
        assert_eq!(
            eval_deadline_budget(now + Duration::from_millis(350), deadline),
            Ok(Duration::from_millis(25))
        );
        assert_eq!(
            eval_deadline_budget(deadline, deadline),
            Err(EvalError::CallbackTimeout)
        );
    }
}

#[cfg(target_os = "macos")]
fn native_snapshot<R: tauri::Runtime>(
    window: &WebviewWindow<R>,
    content: &NativeWebviewContent,
) -> Result<Vec<u8>, String> {
    use block2::RcBlock;
    use objc2::{runtime::AnyObject, MainThreadMarker};
    use objc2_app_kit::{NSBitmapImageFileType, NSBitmapImageRep, NSImage};
    use objc2_foundation::{NSDictionary, NSError, NSNumber, NSPoint, NSRect, NSSize};
    use objc2_web_kit::{WKSnapshotConfiguration, WKWebView};
    use std::ptr::NonNull;

    let (sender, receiver) = mpsc::sync_channel(1);
    let content = *content;
    window
        .with_webview(move |platform| unsafe {
            let Some(marker) = MainThreadMarker::new() else {
                let _ = sender.send(Err(
                    "WKWebView snapshot not dispatched on main thread".into()
                ));
                return;
            };
            let view: &WKWebView = &*platform.inner().cast();
            let configuration = WKSnapshotConfiguration::new(marker);
            configuration.setAfterScreenUpdates(true);
            configuration.setRect(NSRect::new(
                NSPoint::new(content.origin_x, content.origin_y),
                NSSize::new(content.width_points, content.height_points),
            ));
            let snapshot_width = NSNumber::new_f64(content.width_points);
            configuration.setSnapshotWidth(Some(&snapshot_width));
            let block = RcBlock::new(move |image: *mut NSImage, error: *mut NSError| {
                if !error.is_null() || image.is_null() {
                    let _ = sender.send(Err("WKWebView native snapshot callback failed".into()));
                    return;
                }
                let Some(tiff) = (&*image).TIFFRepresentation() else {
                    let _ = sender.send(Err("WKWebView snapshot TIFF unavailable".into()));
                    return;
                };
                let Some(bitmap) = NSBitmapImageRep::imageRepWithData(&tiff) else {
                    let _ = sender.send(Err("WKWebView snapshot bitmap conversion failed".into()));
                    return;
                };
                let properties: objc2::rc::Retained<
                    NSDictionary<objc2_app_kit::NSBitmapImageRepPropertyKey, AnyObject>,
                > = NSDictionary::new();
                let Some(png) = bitmap
                    .representationUsingType_properties(NSBitmapImageFileType::PNG, &properties)
                else {
                    let _ = sender.send(Err("WKWebView snapshot PNG conversion failed".into()));
                    return;
                };
                let length = png.length();
                if length == 0 || length > MAX_SNAPSHOT_BYTES {
                    let _ = sender.send(Err("WKWebView snapshot PNG length invalid".into()));
                    return;
                }
                let mut bytes = vec![0_u8; length];
                png.getBytes_length(NonNull::new_unchecked(bytes.as_mut_ptr().cast()), length);
                let _ = sender.send(Ok(bytes));
            });
            view.takeSnapshotWithConfiguration_completionHandler(Some(&configuration), &block);
        })
        .map_err(|error| format!("WKWebView native snapshot dispatch failed: {error}"))?;
    receiver
        .recv_timeout(Duration::from_secs(30))
        .map_err(|_| "WKWebView native snapshot timed out".to_string())?
}

#[cfg(not(target_os = "macos"))]
fn native_snapshot<R: tauri::Runtime>(
    _window: &WebviewWindow<R>,
    _content: &NativeWebviewContent,
) -> Result<Vec<u8>, String> {
    Err("WKWebView native snapshot unavailable on this platform".into())
}

fn write_output(
    fd: RawFd,
    output: &Value,
    screenshots: &[Vec<u8>],
    nonce: &[u8; 32],
) -> Result<(), String> {
    // SAFETY: ownership of the inherited one-shot descriptor transfers here.
    let mut file = unsafe { File::from_raw_fd(fd) };
    let payload = canonical_bytes(output)?;
    if payload.len() > MAX_UNCOMPRESSED_OUTPUT_JSON_BYTES {
        return Err("native output JSON exceeds uncompressed frame limit".into());
    }
    let mut encoder: GzEncoder<Vec<u8>> = GzBuilder::new()
        .mtime(0)
        .operating_system(255)
        .write(Vec::new(), Compression::new(6));
    encoder
        .write_all(&payload)
        .map_err(|_| "native output JSON compression failed")?;
    let compressed = encoder
        .finish()
        .map_err(|_| "native output JSON compression failed")?;
    if compressed.len() > MAX_COMPRESSED_OUTPUT_JSON_BYTES {
        return Err("native output JSON exceeds compressed frame limit".into());
    }
    let payload_sha256 = sha256_hex(&payload);
    let transport_material = json!({
        "output_frame_magic": "LTG10QA1",
        "output_frame_version": 1,
        "output_frame_codec": OUTPUT_FRAME_CODEC_NAME,
        "output_frame_flags": OUTPUT_FRAME_FLAGS,
        "output_frame_reserved": 0,
        "output_frame_compressed_bytes": compressed.len(),
        "output_frame_uncompressed_bytes": payload.len(),
        "output_frame_raw_json_sha256": payload_sha256,
    });
    let mut response_hasher = Sha256::new();
    response_hasher.update(nonce);
    response_hasher.update(canonical_bytes(&transport_material)?);
    let transport_response = response_hasher.finalize();
    let payload_sha = Sha256::digest(&payload);
    file.write_all(OUTPUT_FRAME_MAGIC)
        .map_err(|_| "output frame magic write failed")?;
    file.write_all(&[OUTPUT_FRAME_CODEC, OUTPUT_FRAME_FLAGS])
        .map_err(|_| "output frame codec write failed")?;
    file.write_all(&OUTPUT_FRAME_RESERVED)
        .map_err(|_| "output frame reserved write failed")?;
    file.write_all(&(compressed.len() as u64).to_be_bytes())
        .map_err(|_| "output header write failed")?;
    file.write_all(&(payload.len() as u64).to_be_bytes())
        .map_err(|_| "output header write failed")?;
    file.write_all(&payload_sha)
        .map_err(|_| "output JSON hash write failed")?;
    file.write_all(&transport_response)
        .map_err(|_| "output transport response write failed")?;
    file.write_all(&compressed)
        .map_err(|_| "output payload write failed")?;
    for screenshot in screenshots {
        file.write_all(&(screenshot.len() as u64).to_be_bytes())
            .map_err(|_| "snapshot header write failed")?;
        file.write_all(screenshot)
            .map_err(|_| "snapshot body write failed")?;
    }
    file.flush()
        .map_err(|_| "output pipe flush failed".to_string())
}

fn add_nonce_response(value: &mut Value, nonce: &[u8; 32], field: &str) -> Result<(), String> {
    let object = value
        .as_object_mut()
        .ok_or("nonce response object invalid")?;
    object.remove(field);
    let mut hasher = Sha256::new();
    hasher.update(nonce);
    hasher.update(canonical_bytes(&Value::Object(object.clone()))?);
    object.insert(
        field.into(),
        Value::String(format!("{:x}", hasher.finalize())),
    );
    Ok(())
}

fn canonical_bytes(value: &Value) -> Result<Vec<u8>, String> {
    fn sorted(value: &Value) -> Value {
        match value {
            Value::Object(object) => {
                let mut keys: Vec<_> = object.keys().collect();
                keys.sort();
                let mut result = Map::new();
                for key in keys {
                    result.insert(key.clone(), sorted(&object[key]));
                }
                Value::Object(result)
            }
            Value::Array(values) => Value::Array(values.iter().map(sorted).collect()),
            _ => value.clone(),
        }
    }
    serde_json::to_vec(&sorted(value)).map_err(|_| "canonical JSON failed".into())
}

fn digest(value: &Value) -> String {
    canonical_bytes(value)
        .map(|bytes| sha256_hex(&bytes))
        .unwrap_or_default()
}

fn sha256_hex(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|_| "executable open failed")?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 1024 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|_| "executable hash read failed")?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn png_dimensions(data: &[u8]) -> Result<(u32, u32), String> {
    const SIGNATURE: &[u8; 8] = b"\x89PNG\r\n\x1a\n";
    if data.len() < 24 || &data[..8] != SIGNATURE || &data[12..16] != b"IHDR" {
        return Err("native snapshot PNG header invalid".into());
    }
    let width = u32::from_be_bytes(data[16..20].try_into().map_err(|_| "PNG width invalid")?);
    let height = u32::from_be_bytes(data[20..24].try_into().map_err(|_| "PNG height invalid")?);
    if width == 0 || height == 0 {
        return Err("native snapshot PNG dimensions invalid".into());
    }
    Ok((width, height))
}

fn valid_hex_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn valid_git_head(value: &str) -> bool {
    value.len() == 40
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn monotonic_ns() -> u64 {
    static ORIGIN: OnceLock<Instant> = OnceLock::new();
    ORIGIN
        .get_or_init(Instant::now)
        .elapsed()
        .as_nanos()
        .try_into()
        .unwrap_or(u64::MAX)
        .max(1)
}
