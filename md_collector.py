import flet as ft
import os
import json
from typing import Dict, List
from controls.collapsible import Collapsible
from datetime import datetime


class WindowControlButton(ft.IconButton):
    """カスタムウィンドウコントロールボタン"""
    def __init__(self, *args, icon_size: int, **kwargs):
        super().__init__(*args, icon_size=icon_size, **kwargs)
        self.height = 30
        self.width = 40
        self.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(),
            color=ft.Colors.ON_SURFACE,
            overlay_color=ft.Colors.SURFACE,
        )


class WindowTitleBar(ft.Stack):
    """カスタムウィンドウタイトルバー"""
    def __init__(self, title: str, page: ft.Page) -> None:
        super().__init__()
        self.page = page
        self.title = title

        # 各種ボタンの初期化
        self.minimize_button = self._create_minimize_button()
        self.maximize_button = self._create_maximize_button()
        self.close_button = self._create_close_button()

    def build(self):
        """タイトルバーUIの構築"""
        return ft.Container(
            content=self._create_title_bar_row(),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _create_title_bar_row(self) -> ft.Row:
        """タイトル部とウィンドウ操作ボタンを並べるRowを作成"""
        return ft.Row(
            controls=[
                self._create_drag_area(),
                self.minimize_button,
                self.maximize_button,
                self.close_button,
            ],
            spacing=0,
        )

    def _create_drag_area(self) -> ft.WindowDragArea:
        """ドラッグ可能なタイトルエリアを作成"""
        return ft.WindowDragArea(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.DESCRIPTION, color=ft.Colors.ON_SURFACE),
                        padding=ft.padding.only(left=5, top=2, bottom=2),
                    ),
                    ft.Text(self.title, color=ft.Colors.ON_SURFACE),
                ],
                height=30,
            ),
            expand=True,
        )

    def _create_minimize_button(self) -> WindowControlButton:
        """最小化ボタンの作成"""
        return WindowControlButton(
            icon=ft.Icons.MINIMIZE_OUTLINED,
            icon_size=13,
            on_click=self.minimize_button_clicked,
        )

    def _create_maximize_button(self) -> WindowControlButton:
        """最大化／元に戻すボタンの作成"""
        return WindowControlButton(
            icon=ft.Icons.SQUARE_OUTLINED,
            icon_size=15,
            on_click=self.maximized_button_clicked,
        )

    def _create_close_button(self) -> WindowControlButton:
        """クローズボタンの作成"""
        return WindowControlButton(
            icon=ft.Icons.CLOSE,
            icon_size=13,
            on_click=lambda _: self.page.window_close(),
        )

    def minimize_button_clicked(self, e):
        """ウィンドウ最小化"""
        self.page.window_minimized = True
        self.page.update()

    def maximized_button_clicked(self, e):
        """最大化／元に戻す"""
        self.page.window_maximized = not self.page.window_maximized
        self.page.update()

    def change_maximized_button_icon(self):
        """ウィンドウ最大化／復元時にボタンアイコンを切り替える"""
        if self.page.window_maximized:
            self.maximize_button.icon = ft.icons.PHOTO_SIZE_SELECT_SMALL
        else:
            self.maximize_button.icon = ft.icons.SQUARE_OUTLINED
        self.update()


CONFIG_FILE = "config.json"

class MarkdownCollector:
    """マークダウンファイルコレクターのメインクラス"""
    def __init__(self, page: ft.Page):
        self.page = page
        
        # ウィンドウ設定
        self.page.window.title_bar_hidden = True
        self.page.window.title_bar_buttons_hidden = True
        self.page.theme_mode = "light"
        self.page.padding = 0
        self.page.theme = ft.Theme()
        
        # 設定を読み込む
        self.config = self._load_config()

        # 設定から復元 or デフォルト値
        self.folder_path = self.config.get("last_folder_path", "")
        self.exclude_patterns = self.config.get("exclude_patterns", {
            'extensions': ['.pyc', '.pyo', '.pyd', '.env'],
            'files': ['.gitignore', '.env', '.DS_Store'],
            'folders': ['venv', '.venv', 'node_modules', '__pycache__', '.git'],
            'max_file_size': 1024 * 1024,  # 1MB
        })

        self.file_paths: List[str] = []
        self.file_info: Dict[str, dict] = {}
        self.check_values: Dict[str, bool] = {}
        self.original_controls = []

        # UI初期化
        self.settings_dialog = None
        self.file_picker = ft.FilePicker(on_result=self.get_folder_result)
        self.page.overlay.append(self.file_picker)
                
        self._init_ui()

        # ウィンドウイベントハンドラーを設定
        self.page.window_event_handlers = {
            "maximize": lambda _: self.title_bar.change_maximized_button_icon(),
            "restore": lambda _: self.title_bar.change_maximized_button_icon(),
        }

        # フォルダパスが既にあるなら自動ロード
        if self.folder_path and os.path.isdir(self.folder_path):
            self.folder_label.value = f"選択されたフォルダ: {self.folder_path}"
            self._load_files()

    def _init_ui(self):
        self.title_bar = WindowTitleBar("Markdown File Collector", self.page)

        self.folder_label = ft.Text(
            "フォルダが選択されていません。",
            size=14,
            color=ft.Colors.GREY_700,
        )

        self.output_text = ft.TextField(
            expand=True,
            read_only=True,
            border=ft.InputBorder.NONE,
            multiline=True,
            min_lines=10,
            max_lines=None,
            text_size=14,
        )

        self.files_column = ft.ListView(
            expand=True,
            spacing=2,
            padding=10,
            auto_scroll=False,
        )

        self.search_box = ft.TextField(
            hint_text="ファイル名で絞り込み...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._filter_files,
            expand=True,
            height=50,
            border_radius=8,
            content_padding=ft.padding.all(10),
        )

        file_toolbar = ft.Row(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.SELECT_ALL,
                                tooltip="全て選択",
                                on_click=self._select_all_files,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DESELECT,
                                tooltip="全て解除",
                                on_click=self._deselect_all_files,
                            ),
                        ],
                        spacing=0,
                    ),
                ),
                ft.Dropdown(
                    options=[
                        ft.dropdown.Option("name_asc", "名前 (昇順)"),
                        ft.dropdown.Option("name_desc", "名前 (降順)"),
                        ft.dropdown.Option("date_asc", "更新日時 (昇順)"),
                        ft.dropdown.Option("date_desc", "更新日時 (降順)"),
                        ft.dropdown.Option("size_asc", "サイズ (昇順)"),
                        ft.dropdown.Option("size_desc", "サイズ (降順)"),
                    ],
                    value="name_asc",
                    on_change=self._sort_files,
                    width=150,
                    height=50,
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
        )

        toolbar_container = ft.Container(
            content=ft.Row(
                [
                    self.search_box,
                    file_toolbar,
                ],
                spacing=10,
            ),
            margin=ft.margin.only(bottom=10),
            height=60,
            alignment=ft.alignment.center,
        )

        header_container = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        "Markdown出力",
                        size=16,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.BLUE_700,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "クリップボードにコピー",
                                icon=ft.Icons.COPY,
                                on_click=self.copy_to_clipboard,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "保存",
                                icon=ft.Icons.SAVE,
                                on_click=self.save_markdown,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                height=50,
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=10,
            ),
            margin=ft.margin.only(bottom=10),
            height=60,
            alignment=ft.alignment.center,
        )

        files_section = ft.Container(
            content=ft.Column([
                toolbar_container,
                ft.Container(
                    content=ft.Column(
                        [self.files_column],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=8,
                    expand=True,
                ),
            ], spacing=0),
            expand=True,
        )

        output_section = ft.Container(
            content=ft.Column([
                header_container,
                ft.Container(
                    content=self.output_text,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=8,
                    padding=10,
                    expand=True,
                ),
            ], spacing=0),
            expand=True,
        )

        main_content = ft.Row(
            [
                ft.Container(content=files_section, expand=1),
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Container(content=output_section, expand=1),
            ],
            expand=True,
            spacing=20,
        )

        folder_selection = ft.Container(
            content=ft.Row(
                [
                    ft.ElevatedButton(
                        "フォルダを選択",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=self.select_folder,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                    ft.Container(
                        content=self.folder_label,
                        expand=True,
                        padding=ft.padding.only(left=10),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        tooltip="除外設定",
                        on_click=self.show_settings,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(bottom=20),
        )

        content_container = ft.Container(
            content=ft.Column(
                [
                    folder_selection,
                    ft.Container(content=main_content, expand=True),
                ],
                spacing=0,
                expand=True,
            ),
            padding=15,
            expand=True,
        )

        self.page.add(
            ft.Column(
                [
                    self.title_bar,
                    content_container,
                ],
                spacing=0,
                expand=True,
            )
        )

    def select_folder(self, e):
        self.file_picker.get_directory_path()

    def get_folder_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.folder_path = e.path
            self.folder_label.value = f"選択されたフォルダ: {self.folder_path}"
            self._load_files()
            self.page.update()

    def _load_files(self):
        self.files_column.controls.clear()
        self.check_values.clear()
        self.file_paths = []
        self.file_info.clear()
        self.original_controls.clear()

        if not os.path.isdir(self.folder_path):
            self.page.update()
            return

        try:
            self._load_directory(self.folder_path, self.files_column.controls)
        except Exception as e:
            self._show_error(f"ファイル一覧の読み込みに失敗: {e}")

        self.original_controls = self.files_column.controls.copy()

        # ソート & 更新
        self._sort_files()
        self.page.update()

        # 最後に選択したフォルダを設定ファイルに保存
        self.config["last_folder_path"] = self.folder_path
        self._save_config()

    def _load_directory(self, directory: str, controls: list):
        items = os.listdir(directory)
        items = [item for item in items if not self._should_exclude(os.path.join(directory, item), item)]
        
        folders = sorted([i for i in items if os.path.isdir(os.path.join(directory, i))])
        files = sorted([i for i in items if os.path.isfile(os.path.join(directory, i))])

        for folder in folders:
            folder_path = os.path.join(directory, folder)
            folder_controls = []
            self._load_directory(folder_path, folder_controls)
            if folder_controls:  # 中身がある場合のみ
                collapsible = Collapsible(
                    title=folder,
                    icon=ft.Icon(ft.Icons.FOLDER, color=ft.Colors.BLUE_700),
                    content=ft.Column(controls=folder_controls, spacing=2)
                )
                collapsible.on_folder_checked = lambda c=collapsible: self._update_folder_state(c)
                controls.append(collapsible)

        for file in files:
            file_path = os.path.join(directory, file)
            stat = os.stat(file_path)
            self.file_info[file_path] = {
                "name": file,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
            c = ft.Container(
                content=ft.Row(
                    [
                        ft.Checkbox(
                            value=False,
                            data=file_path,
                            on_change=self.checkbox_changed,
                            scale=1.2,
                        ),
                        ft.Column(
                            [
                                ft.Text(file, size=14, weight=ft.FontWeight.W_500),
                                ft.Text(
                                    f"更新: {self._format_date(stat.st_mtime)} - サイズ: {self._format_size(stat.st_size)}",
                                    size=12, color=ft.Colors.GREY_700
                                ),
                            ],
                            spacing=2, expand=True
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=5, vertical=8),
                border_radius=8,
            )
            controls.append(c)
            self.check_values[file_path] = False
            self.file_paths.append(file_path)

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _format_date(self, ts: float) -> str:
        return datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")

    def _filter_files(self, e):
        search_text = self.search_box.value.strip().lower()
        if not search_text:
            # フィルタ解除 → 全てを元に戻す
            for c in self.original_controls:
                if isinstance(c, Collapsible):
                    c.restore_original_state()
            self.files_column.controls = self.original_controls.copy()
            self.page.update()
            return

        # フィルタ適用
        filtered = []
        for c in self.original_controls:
            if isinstance(c, Collapsible):
                c.restore_original_state()
                if c.apply_filter(search_text):
                    filtered.append(c)
            else:
                file_path = c.content.controls[0].data
                file_name = os.path.basename(file_path).lower()
                if search_text in file_name:
                    filtered.append(c)
        self.files_column.controls = filtered
        self.page.update()

    def _sort_files(self, e=None):
        if not self.files_column.controls:
            return

        sort_key = e.control.value if e else "name_asc"
        controls = self.files_column.controls.copy()

        folders = []
        files = []
        for c in controls:
            if isinstance(c, Collapsible):
                folders.append(c)
            else:
                files.append(c)

        def get_sort_value(c):
            if isinstance(c, Collapsible):
                return c.title.lower()
            else:
                path = c.content.controls[0].data
                info = self.file_info[path]
                if sort_key.startswith("name"):
                    return info["name"].lower()
                elif sort_key.startswith("date"):
                    return info["modified"]
                else:  # size
                    return info["size"]

        reverse = sort_key.endswith("desc")
        folders.sort(key=get_sort_value, reverse=reverse)
        files.sort(key=get_sort_value, reverse=reverse)

        self.files_column.controls = folders + files
        if not self.search_box.value.strip():
            self.original_controls = self.files_column.controls.copy()
        self.page.update()

    def _select_all_files(self, e):
        for c in self.files_column.controls:
            if isinstance(c, Collapsible):
                c.set_files_checked(True)
                for file_c in c.get_all_files():
                    cb = file_c.content.controls[0]
                    self.check_values[cb.data] = True
                    cb.value = True
                    cb.update()
            else:
                cb = c.content.controls[0]
                cb.value = True
                self.check_values[cb.data] = True
                cb.update()
        self.update_markdown_output()
        self.page.update()

    def _deselect_all_files(self, e):
        for c in self.files_column.controls:
            if isinstance(c, Collapsible):
                c.set_files_checked(False)
                for file_c in c.get_all_files():
                    cb = file_c.content.controls[0]
                    self.check_values[cb.data] = False
                    cb.value = False
                    cb.update()
            else:
                cb = c.content.controls[0]
                cb.value = False
                self.check_values[cb.data] = False
                cb.update()
        self.update_markdown_output()
        self.page.update()

    def checkbox_changed(self, e):
        """個々のファイルのチェックボックスが切り替わった"""
        self.check_values[e.control.data] = e.control.value
        # 親フォルダがあれば三状態再計算
        self._recalc_parent_folders()
        self.update_markdown_output()
        self.page.update()

    def _update_folder_state(self, folder: Collapsible):
        """
        フォルダ全体をセットした場合(IconButtonクリックで全ON/全OFFされたとき)の処理。
        """
        # 全配下ファイルの状態を self.check_values に反映
        for file_c in folder.get_all_files():
            cb = file_c.content.controls[0]
            self.check_values[cb.data] = (folder._folder_state is True)

        # 親フォルダの三状態再計算
        self._recalc_parent_folders()
        self.update_markdown_output()
        self.page.update()

    def _recalc_parent_folders(self):
        """
        全フォルダについて三状態チェックを再計算してアップデート。
        """
        # すべての Collapsible を走査
        def recurse(c):
            if isinstance(c, Collapsible):
                for sub in c.content.controls:
                    recurse(sub)
                c.recalc_folder_state()

        for top_c in self.files_column.controls:
            recurse(top_c)

    def update_markdown_output(self):
        tree = self._generate_tree_structure()
        docs = []
        for path, checked in self.check_values.items():
            if checked:
                rel_path = os.path.relpath(path, self.folder_path)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    docs.append(f"## {rel_path}\n```\n{content}\n```")
                except Exception as err:
                    docs.append(f"## {rel_path}\n```\nエラー: {err}\n```")
        self.output_text.value = tree + "\n".join(docs)

    def _generate_tree_structure(self) -> str:
        """選択されたファイルのパスをもとにASCIIツリーを生成"""
        def add_to_tree(path: str, tree: dict):
            parts = os.path.normpath(path).split(os.sep)
            current = tree
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    current[part] = None
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        tree = {}
        for path, checked in self.check_values.items():
            if checked:
                rel = os.path.relpath(path, self.folder_path)
                add_to_tree(rel, tree)

        if not tree:
            return ""

        def build_str(subtree: dict, prefix: str=""):
            lines = []
            items = sorted(subtree.items())
            for i, (name, val) in enumerate(items):
                is_last = (i == len(items)-1)
                connector = "└── " if is_last else "├── "
                lines.append(prefix + connector + name)
                if val is not None:
                    extension = "    " if is_last else "│   "
                    lines.append(build_str(val, prefix+extension))
            return "\n".join(lines)

        root_name = os.path.basename(self.folder_path)
        text = f"# Directory Structure\n```\n{root_name}\n"
        text += build_str(tree)
        text += "\n```\n\n"
        return text

    def save_markdown(self, e):
        text = self.output_text.value.strip()
        if not text:
            self._show_error("保存するテキストがありません。")
            return
        picker = ft.FilePicker(on_result=self.save_file_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.save_file(
            initial_directory=self.folder_path if self.folder_path else ".",
            file_name="output.md"
        )

    def save_file_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f:
                    f.write(self.output_text.value)
                self._show_success(f"保存しました: {e.path}")
            except Exception as err:
                self._show_error(f"保存失敗: {err}")
            self.page.update()

    def copy_to_clipboard(self, e):
        text = self.output_text.value.strip()
        if not text:
            self._show_error("コピーするテキストがありません。")
            return
        self.page.set_clipboard(text)
        self._show_success("クリップボードにコピーしました。")

    def show_settings(self, e):
        # 現在の値をフォームにセット
        exts = self.exclude_patterns.get("extensions", [])
        files_ = self.exclude_patterns.get("files", [])
        folds = self.exclude_patterns.get("folders", [])
        max_sz = self.exclude_patterns.get("max_file_size", 1024*1024) / (1024*1024)

        extensions_field = ft.TextField(
            label="除外する拡張子",
            value=", ".join(exts),
            multiline=True,
            min_lines=2,
        )
        files_field = ft.TextField(
            label="除外するファイル名",
            value=", ".join(files_),
            multiline=True,
            min_lines=2,
        )
        folders_field = ft.TextField(
            label="除外するフォルダ名",
            value=", ".join(folds),
            multiline=True,
            min_lines=2,
        )
        max_size_field = ft.TextField(
            label="最大ファイルサイズ(MB)",
            value=str(max_sz),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
        )

        def save_settings(ev):
            # テキストフィールドの内容を設定に反映
            self.exclude_patterns["extensions"] = [x.strip() for x in extensions_field.value.split(",") if x.strip()]
            self.exclude_patterns["files"] = [x.strip() for x in files_field.value.split(",") if x.strip()]
            self.exclude_patterns["folders"] = [x.strip() for x in folders_field.value.split(",") if x.strip()]
            try:
                mb = float(max_size_field.value)
                self.exclude_patterns["max_file_size"] = int(mb * 1024 * 1024)
            except:
                self.exclude_patterns["max_file_size"] = 1024*1024
            
            # 設定をファイルへ保存
            self.config["exclude_patterns"] = self.exclude_patterns
            self._save_config()

            # フォルダが選択されているなら再読み込み
            if self.folder_path:
                self._load_files()

            # ダイアログを閉じる
            self._close_settings()

        # 既存のダイアログがあれば閉じる
        if self.settings_dialog:
            self._close_settings()

        self.settings_dialog = ft.AlertDialog(
            title=ft.Text("除外設定"),
            content=ft.Column(
                [
                    extensions_field,
                    files_field,
                    folders_field,
                    max_size_field,
                ],
                tight=True,
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
                width=600,
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda _: self._close_settings()),
                ft.TextButton("保存", on_click=save_settings),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )

        # ダイアログを表示
        # self.page.dialog = self.settings_dialog
        self.page.overlay.append(self.settings_dialog)
        self.settings_dialog.open = True
        self.page.update()

    def _close_settings(self):
        if self.settings_dialog:
            self.page.close(self.settings_dialog)

    def _should_exclude(self, path: str, name: str) -> bool:
        # 拡張子チェック
        if any(name.endswith(ext) for ext in self.exclude_patterns['extensions']):
            return True
        # ファイル名
        if name in self.exclude_patterns['files']:
            return True
        # フォルダ名
        if os.path.isdir(path) and name in self.exclude_patterns['folders']:
            return True
        # サイズ
        if os.path.isfile(path):
            try:
                if os.path.getsize(path) > self.exclude_patterns['max_file_size']:
                    return True
            except:
                return True
        return False

    def _show_error(self, msg: str):
        sb = ft.SnackBar(content=ft.Text(msg, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED)
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()
        self.page.overlay.remove(sb)

    def _show_success(self, msg: str):
        sb = ft.SnackBar(content=ft.Text(msg, color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN)
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()
        self.page.overlay.remove(sb)

    # ------------------------------
    # JSON 設定ファイル (config.json)
    # ------------------------------
    def _load_config(self) -> dict:
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as err:
            print(f"設定ファイルの保存に失敗: {err}")

def main(page: ft.Page):
    MarkdownCollector(page)

if __name__ == "__main__":
    ft.app(target=main)
