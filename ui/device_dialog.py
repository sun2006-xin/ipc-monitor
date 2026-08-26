from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QCheckBox, QHBoxLayout

class DeviceDialog(QDialog):
    def __init__(self, device=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加/编辑设备")
        self.device = device or {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.device.get("name", ""))
        form.addRow("设备名称:", self.name_edit)

        self.ip_edit = QLineEdit()
        self.ip_edit.setText(self.device.get("ip", ""))
        form.addRow("IP 地址:", self.ip_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setText(self.device.get("password", ""))
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("密码:", self.password_edit)

        self.stream_edit = QLineEdit()
        self.stream_edit.setText(self.device.get("stream", "stream1"))
        form.addRow("流名称:", self.stream_edit)

        self.online_check = QCheckBox("在线")
        self.online_check.setChecked(self.device.get("online", True))
        form.addRow("状态:", self.online_check)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def get_device(self):
        return {
            "name": self.name_edit.text(),
            "ip": self.ip_edit.text(),
            "password": self.password_edit.text(),
            "stream": self.stream_edit.text(),
            "online": self.online_check.isChecked()
        }