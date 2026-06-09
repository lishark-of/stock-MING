fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running stock-MING Command Center 3.0");
}
