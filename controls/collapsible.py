import flet as ft
import os
from math import pi

class Collapsible(ft.Stack):
    def __init__(self, title: str, icon: ft.Icon, content: ft.Column):
        super().__init__()
        self.title = title
        self.icon = icon
        self.content = content
        
        # フォルダの内部チェック状態(三状態):
        #  - True     = すべてON
        #  - False    = すべてOFF
        #  - None     = 一部のみON
        self._folder_state = False  
        
        # 開閉状態
        self._expanded = False

        # 元の全子コントロールを保持(フィルタ復元に使用)
        self._original_controls = content.controls.copy()
        
        # コールバック(親に通知するため)
        self.on_folder_checked = None

    def build(self):
        self.arrow = ft.Icon(
            name=ft.Icons.KEYBOARD_ARROW_DOWN,
            size=20,
            color=ft.Colors.GREY_700,
            rotate=0,
        )
        
        self.content.visible = self._expanded

        # フォルダのチェックボックスはアイコン切り替えで三状態を表現
        self.folder_checkbox = ft.IconButton(
            icon=self._get_icon_by_state(),
            on_click=self._folder_checkbox_clicked,
        )

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    self.folder_checkbox,
                                    self.icon,
                                    ft.Text(
                                        value=self.title,
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.GREY_800,
                                    ),
                                ],
                                spacing=5,
                            ),
                            self.arrow,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=5),
                    border_radius=8,
                    on_click=self._toggle_expanded,
                    bgcolor=ft.Colors.SURFACE,
                    ink=True,
                ),
                ft.Container(
                    content=self.content,
                    padding=ft.padding.only(left=32),
                ),
            ],
            spacing=0,
        )

    def restore_original_state(self):
        """フィルタ前の状態に復元"""
        self.content.controls = self._original_controls.copy()
        for control in self.content.controls:
            if isinstance(control, Collapsible):
                control.restore_original_state()

    def apply_filter(self, search_text: str) -> bool:
        """フォルダ／ファイル名による再帰的フィルタ"""
        self.restore_original_state()
        folder_name_match = (search_text in self.title.lower())

        filtered_controls = []
        for c in self.content.controls:
            if isinstance(c, Collapsible):
                if c.apply_filter(search_text):
                    filtered_controls.append(c)
            else:
                file_path = c.content.controls[0].data
                file_name = os.path.basename(file_path).lower()
                if search_text in file_name:
                    filtered_controls.append(c)

        if folder_name_match:
            # フォルダ名がマッチしているなら全て残す
            pass
        else:
            self.content.controls = filtered_controls

        has_visible_files = folder_name_match or (len(filtered_controls) > 0)
        return has_visible_files

    def get_all_files(self):
        """フォルダ配下のファイルを再帰的に取得"""
        files = []
        for c in self.content.controls:
            if isinstance(c, Collapsible):
                files.extend(c.get_all_files())
            else:
                files.append(c)
        return files

    def set_files_checked(self, checked: bool):
        """
        フォルダ配下の全ファイルを一括でON/OFF。
        三状態のうち「全部ON or 全部OFF」のときに呼ばれる。
        """
        self._folder_state = checked  # True or False
        self.folder_checkbox.icon = self._get_icon_by_state()
        self.folder_checkbox.update()

        # 配下を全部同じに
        for c in self.content.controls:
            if isinstance(c, Collapsible):
                c.set_files_checked(checked)
            else:
                checkbox = c.content.controls[0]
                checkbox.value = checked
                if checkbox.on_change:
                    fake_event = type('Event', (), {'control': checkbox})()
                    checkbox.on_change(fake_event)
                checkbox.update()

        self.update()

    def recalc_folder_state(self):
        """
        下位ファイル・フォルダの状態から自分の三状態を再計算。
        """
        all_files = self.get_all_files()
        if not all_files:
            # 下位にファイルが無ければ「未選択」として扱う
            self._folder_state = False
        else:
            values = []
            for file_control in all_files:
                cb = file_control.content.controls[0]
                values.append(bool(cb.value))

            all_on = all(values)
            none_on = not any(values)

            if all_on:
                self._folder_state = True
            elif none_on:
                self._folder_state = False
            else:
                self._folder_state = None  # 一部のみ

        self.folder_checkbox.icon = self._get_icon_by_state()
        self.folder_checkbox.update()

    def _get_icon_by_state(self):
        """_folder_state (三状態) に対応するアイコンを返す"""
        if self._folder_state is True:
            return ft.Icons.CHECK_BOX
        elif self._folder_state is False:
            return ft.Icons.CHECK_BOX_OUTLINE_BLANK
        else:
            return ft.Icons.INDETERMINATE_CHECK_BOX  # None → 部分チェック

    def _toggle_expanded(self, e):
        # 開閉切り替え
        if e is not None and hasattr(e, "control") and e.control == self.folder_checkbox:
            # アイコンボタンをクリックした場合はここで処理しない
            return
        self._expanded = not self._expanded
        self.content.visible = self._expanded
        self.arrow.rotate = pi if self._expanded else 0
        self.arrow.update()
        self.update()

    def _folder_checkbox_clicked(self, e):
        """
        フォルダのアイコンボタン（チェックボックス）をクリックしたときの処理。
        状態を次にローテーションさせる or UIとしては単に「全ON/全OFF切り替え」でもOK。
        """
        if self._folder_state is True:
            # すべてON → すべてOFFへ
            self.set_files_checked(False)
        else:
            # すべてOFFまたは部分 → すべてONへ
            self.set_files_checked(True)

        # 親へ通知
        if self.on_folder_checked:
            self.on_folder_checked()
