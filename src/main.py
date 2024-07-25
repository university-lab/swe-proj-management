from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QListWidgetItem, QTableWidgetItem, QDialog
)
from PyQt5.QtCore import QTimer, QDate
from PyQt5 import uic

from db import (
    Database, User, ProjectEntry, HistoricalProject
)

import utils
import os


g_database = Database(
    uri=os.environ['SQL_URI'],
    #drop_before_load=True
)


def ui_path(s):
    return os.path.join("src", "res", f"{s}.ui")


class ChangeProjectUsers(QDialog):
    def __init__(self, user_id, project_id, revision_id, parent=None):
        super().__init__(parent)
        uic.loadUi(ui_path("modify-users"), self)
        
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_confirm.clicked.connect(self.close)
        self.btn_add.clicked.connect(self.add_user)
        self.btn_remove.clicked.connect(self.remove_user)

        self.cancelled = False
        self.user_id = user_id

        self.project = g_database.get_project(
            ProjectEntry.id == project_id
        )
        self.revision = self.project.get(revision_id)
        self.current_users = set(
            user.user_id for user in self.revision.project_users
        )
        self.all_users = set(
            user.id for user in g_database.users.get_all()
        ) - self.current_users

        self._populate_tables()

    def cancel(self):
        self.cancelled = True
        self.close()

    def remove_user(self):
        if not self.current_users:
            return
        user_to_remove = self.list_allowed.selectedItems()[0]
        if (id := user_to_remove.value) == self.project.owner_id:
            return
        if id == self.user_id:
            return
        self.all_users.add(id)
        self.current_users -= self.all_users
        self._populate_tables()

    def add_user(self):
        if not self.all_users:
            return
        user_to_add = self.list_all.selectedItems()[0]
        self.current_users.add(user_to_add.value)
        self.all_users -= self.current_users
        self._populate_tables()

    def _populate_tables(self):
        self.list_all.clear()
        self.list_allowed.clear()

        for id in self.current_users:
            user = g_database.users.get(User.id == id)
            list_item = QListWidgetItem(user.full_name or user.username)
            list_item.value = id
            self.list_allowed.addItem(list_item)

        for id in self.all_users:
            user = g_database.users.get(User.id == id)
            list_item = QListWidgetItem(user.full_name or user.username)
            list_item.value = id
            self.list_all.addItem(list_item)


class ConfirmDialog(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        uic.loadUi(ui_path("dialog"), self)
        self.label_confirm.setText(text)
        self.btn_cancel.clicked.connect(lambda: self.submitted(False))
        self.btn_confirm.clicked.connect(lambda: self.submitted(True))
        self.confirmed = None

    def submitted(self, value):
        self.confirmed = value
        self.close()


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(ui_path("help"), self)
        self.btn_close.clicked.connect(self.close)


class MainForm(QMainWindow):
    _s = {
        "updated_name": "Your name has been updated",
        "refresh_db": "Database components refreshed",
        "revision_loaded": "Project revision loaded",
        "created_entry": "Created new project entry",
        "view_remove_entry_permission":
            "You must be the project creator to remove this revision",
        "view_remove_entry_ok": "Removed revision successfully",
        "view_remove_entry_last":
            "You cannot remove the last remaining revision",
        "view_entry_modified": "Created new revision successfully",
        "view_users_modified": "Changed project userlist",
        "view_modify_permissions": "You don't have permissions to modify "
            "this project"
    }

    def __init__(self, user_object):
        super().__init__()
        uic.loadUi(ui_path("interface"), self)

        self.user_object = user_object
        self.logs = []

        self._register_tab("action_create_entry", 2)
        self._register_tab("action_logs", 4)
        self._register_tab("action_preferences", 3)
        self._register_tab("action_entries", 0)

        self.action_help.triggered.connect(self.open_help)
        self.action_logout.triggered.connect(self.logout)
        self.action_refresh.triggered.connect(self._refresh_db_components)

        self.btn_create_entry.clicked.connect(self.create_entry)
        self.btn_update_pref.clicked.connect(self.update_preferences)
        self.btn_view_edit.clicked.connect(self.toggle_view_edit_state)
        self.btn_clear_logs.clicked.connect(self.clear_logs)
        self.btn_view_remove.clicked.connect(self.edit_remove_entry)
        self.btn_view_modify_users.clicked.connect(self.edit_modify_users)
        self.btn_view_confirm.clicked.connect(self.edit_confirm_changes)

        self.table_entries.cellDoubleClicked.connect(self.row_double_clicked)
        self.table_revision.itemSelectionChanged.connect(self.revision_selected)

        self._refresh_db_components()

    def _refresh_db_components(self):
        self._view__populate_projects()
        self._create__populate_users()
        self._pref__populate()
        self._logs_populate()

    def _pref__populate(self):
        self.pref_username.setText(self.user_object.username)
        self.pref_name.setText(self.user_object.full_name or "")

    def _logs_populate(self):
        self.list_logs.clear()
        self.list_logs.addItems(self.logs)

    def clear_logs(self):
        self.logs = []
        self._refresh_db_components()

    def _create__populate_users(self):
        self.create_project_users.clear()
        for user in g_database.users.get_all():
            if user.id == self.user_object.id:
                continue
            item = QListWidgetItem(user.full_name or user.username)
            item.value = user.id
            self.create_project_users.addItem(item)

    def _view__populate_projects(self):
        self.table_entries.setRowCount(
            len(projects := g_database.get_projects())
        )

        for idx, project in enumerate(projects):
            created_at = QTableWidgetItem(
                str(project.get_history()[0].created_at)
            )
            latest_project = project.get_latest()
            created_at.value = project.id
            self.table_entries.setItem(idx, 0, created_at)
            self.table_entries.setItem(
                idx,
                1, QTableWidgetItem(str(latest_project.created_at))
            )
            author = g_database.users.get(User.id == project.owner_id)
            self.table_entries.setItem(
                idx,
                2, QTableWidgetItem(author.username or author.full_name)
            )
            self.table_entries.setItem(
                idx,
                3, QTableWidgetItem(latest_project.urgency)
            )
            self.table_entries.setItem(
                idx,
                4, QTableWidgetItem(str(latest_project.deadline))
            )

    def _edit__clear(self, *, clear_revisions=True):
        if clear_revisions:
            self.table_revision.itemSelectionChanged.disconnect()
            self.table_revision.setRowCount(0)
            self.table_revision.itemSelectionChanged.connect(
                self.revision_selected
            )
        self.view_urgency.setText("")
        self.view_deadline.setDate(QDate(1970, 1, 1))
        self.view_notes.setPlainText("")
        if self.btn_view_edit.isChecked():
            self.btn_view_edit.toggle()
            self.toggle_view_edit_state()
        self.list_project_users.clear()

    def _edit__load_project(self, id):
        self._edit__clear()
        project = g_database.get_project(ProjectEntry.id == id)
        base_project = g_database.get_project(
            ProjectEntry.id == id
        )
        self.table_revision.setRowCount(
            len(history := project.get_history())
        )
        for idx, revision in enumerate(history):
            user = g_database.users.get(User.id == revision.created_by)
            created = QTableWidgetItem(str(revision.created_at))
            created.value = revision
            self.table_revision.setItem(idx, 0, created)
            self.table_revision.setItem(
                idx,
                1, QTableWidgetItem(user.full_name or user.username)
            )
        self.table_revision.selectRow(idx)
        if not base_project.has_user(self.user_object.id):
            self.btn_view_edit.setEnabled(False)
            self.btn_view_edit.setText("Read-only")
        else:
            self.btn_view_edit.setEnabled(True)
            self.btn_view_edit.setText("Edit")

    def _register_tab(self, name, to):
        getattr(self, name).triggered.connect(lambda: self.change_tab(to))

    def _edit__get_selected_revision(self):
        item = self.table_revision.selectedItems()
        if not item:
            return
        return item[0].value

    def set_status_message(self, s):
        self.status_bar.showMessage((msg := self._s[s]), 2000)
        self.logs.append(msg)

    def toggle_view_edit_state(self):
        to = self.btn_view_edit.isChecked()
        self.btn_view_modify_users.setEnabled(to)
        self.btn_view_remove.setEnabled(to)
        self.btn_view_confirm.setEnabled(to)
        self.view_notes.setEnabled(to)
        self.view_urgency.setEnabled(to)
        self.view_deadline.setEnabled(to)
        self.list_project_users.setEnabled(to)

    def edit_remove_entry(self):
        confirm_dialog = ConfirmDialog(
            "Are you sure you want to remove this revision?",
            self
        )
        confirm_dialog.exec_()
        if not confirm_dialog.confirmed:
            return
        project = self._edit__get_selected_revision()
        base_project = g_database.get_project(
            ProjectEntry.id == project.project_id
        )
        if self.user_object.id != base_project.owner_id:
            self.set_status_message("view_remove_entry_permission")
            return
        try:
            base_project.remove(HistoricalProject.id == project.id)
        except ValueError:
            self.set_status_message("view_remove_entry_last")
            return
        self.set_status_message("view_remove_entry_ok")
        self._refresh_db_components()
        self._edit__load_project(base_project.id)

    def edit_modify_users(self):
        project = self._edit__get_selected_revision()
        base_project = g_database.get_project(
            ProjectEntry.id == project.project_id
        )
        change_dialog = ChangeProjectUsers(
            self.user_object.id, base_project.id, project.id, self
        )
        change_dialog.exec_()

        if change_dialog.cancelled:
            return

        self.list_project_users.clear()
        for allowed_id in change_dialog.current_users:
            user = g_database.users.get(User.id == allowed_id)
            list_item = QListWidgetItem(user.full_name or user.username)
            list_item.value = user.id
            self.list_project_users.addItem(list_item)

        self.set_status_message("view_users_modified")

    def edit_confirm_changes(self):
        project = self._edit__get_selected_revision()
        base_project = g_database.get_project(
            ProjectEntry.id == project.project_id
        )
        base_project.update(self.user_object.id, **{
            "notes": self.view_notes.toPlainText(),
            "deadline": self.view_deadline.dateTime().toPyDateTime(),
            "urgency": self.view_urgency.text(),
            "users": [
                self.list_project_users.item(i).value
                for i in range(self.list_project_users.count())
            ]
        })
        self.set_status_message("view_entry_modified")
        self._refresh_db_components()
        self._edit__load_project(base_project.id)

    def revision_selected(self):
        self._edit__clear(clear_revisions=False)
        project = self._edit__get_selected_revision()
        if project is None:
            return
        self.set_status_message("revision_loaded")
        self.view_urgency.setText(project.urgency)
        self.view_deadline.setDate(QDate(project.deadline))
        self.view_notes.setPlainText(project.notes)
        for project_user in project.project_users:
            user = g_database.users.get(User.id == project_user.user_id)
            list_item = QListWidgetItem(
                user.full_name or user.username
            )
            list_item.value = user.id
            self.list_project_users.addItem(list_item)

    def update_preferences(self):
        full_name = self.pref_name.text()
        g_database.users.update(self.user_object.id, full_name=full_name)
        self.set_status_message("updated_name")
        self._refresh_db_components()

    def row_double_clicked(self, which):
        project_id = self.table_entries.item(which, 0).value
        self._edit__load_project(project_id)
        self.change_tab(1)

    def open_help(self):
        self._help_dialog = HelpDialog(self)
        self._help_dialog.exec_()

    def logout(self):
        self.user_object = None
        self._start_dialog = StartupDialog(just_logged_out=True)
        self._start_dialog.show()
        self.close()

    def create_entry(self):
        selected_user_ids = [
            item.value for item in self.create_project_users.selectedItems()
        ]
        notes = self.create_notes.toPlainText()
        urgency = self.create_urgency.text()
        deadline = self.create_deadline.dateTime().toPyDateTime()
        project = g_database.create_project(
            self.user_object.id,
            notes=notes, urgency=urgency, deadline=deadline,
            users=selected_user_ids
        )
        self._refresh_db_components()
        self._edit__load_project(project.id)
        self.set_status_message("created_entry")
        self.change_tab(1)

    def change_tab(self, to):
        self._refresh_db_components()
        self.tab_widget.setCurrentIndex(to)


class StartupDialog(QMainWindow):
    _s = {
        "login_fail": "Invalid username/password combination",
        "fields_empty": "The username/password fields must be nonempty",
        "reg_verify": "The passwords do not match",
        "reg_existing": "Username already exists",
        "cache_invalid": "Saved login is invalid",
    }
    LOGIN_CACHE_PATH = "./.mgmt-login"

    def __init__(self, *, just_logged_out=False):
        super().__init__()
        utils.add_font_resource(":/fonts/cmunss.ttf")
        uic.loadUi(ui_path("start"), self)

        self.user_object = None

        self.btn_login.clicked.connect(self.on_login)
        self.btn_register.clicked.connect(self.on_register)

        if not just_logged_out:
            self._try_login_from_cache()

    def _login(self, username, password):
        try:
            potential = g_database.users.get(User.username == username)
        except IndexError:
            self.set_status_message("login_fail")
            return False
        if utils.hash_password(password) != potential.password_hash:
            self.set_status_message("login_fail")
            return False
        self.user_object = potential
        if self.is_remember_me_checked():
            self._create_login_cache(username, password)
        return True

    def _create_login_cache(self, username, password):
        with open(self.LOGIN_CACHE_PATH, "w") as out:
            out.write(f"{username}\n{password}")

    def _try_login_from_cache(self):
        if not os.path.exists(self.LOGIN_CACHE_PATH):
            return
        with open(self.LOGIN_CACHE_PATH) as f_login:
            username, password = f_login.read().splitlines()
        if not self._login(username, password):
            self.set_status_message("cache_invalid")
            return
        self.open_main_interface()

    def is_remember_me_checked(self):
        return self.cb_remember_me.isChecked()

    def set_status_message(self, s):
        self.status_bar.showMessage(self._s[s], 4000)

    def on_login(self):
        self.user_object
        username = self.login_username.text()
        password = self.login_password.text()
        if not username or not password:
            self.set_status_message("fields_empty")
            return
        if self._login(username, password):
            self.open_main_interface()

    def on_register(self):
        self.user_object
        username = self.reg_username.text()
        password = self.reg_password.text()
        verify_password = self.reg_verify.text()
        if not username or not password or not verify_password:
            self.set_status_message("fields_empty")
            return
        if password != verify_password:
            self.set_status_message("reg_verify")
            return
        try:
            g_database.users.get(User.username == username)
            self.set_status_message("reg_existing")
            return
        except IndexError:
            pass
        g_database.users.create(
            username=username,
            password_hash=utils.hash_password(password)
        )
        if self._login(username, password):
            self.open_main_interface()

    def open_main_interface(self):
        self.main_form = MainForm(self.user_object)
        self.main_form.show()
        QTimer.singleShot(0, self.close)


if __name__ == '__main__':
    app = QApplication([])
    window = StartupDialog()
    window.show()
    app.exec()
