from dataclasses import dataclass, field
import re
import sys
import textwrap
import traceback
from typing import Literal

from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox,
    QTextEdit, QPushButton, QLabel, QMessageBox, QHBoxLayout, QSizePolicy, QPlainTextEdit
)
from PySide6.QtGui import QFont, QPalette, QColor
from pygments import highlight
from pygments.lexers.python import PythonLexer
from pygments.formatters import HtmlFormatter
import sqlglot
from sqlglot import exp
import sqlglot.dialects.sqlite      # avoid pyinstall pack failed
import sqlglot.dialects.postgres
import sqlglot.dialects.mysql
import sqlglot.dialects.snowflake
import sqlglot.dialects.redshift
import sqlglot.dialects.bigquery
import sqlglot.dialects.duckdb
import pyperclip


@dataclass
class SQLItem:

    name: str
    type: str
    is_primary: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    is_index: bool = False
    default: str = None
    comment: str = None

@dataclass
class TableConstraintItem:
    type: Literal["UniqueConstraint",]
    name: str
    cols: list = field(default_factory=list)

@dataclass
class TableIndexItem:
    type: Literal["normal",]
    name: str
    cols: list = field(default_factory=list)


@dataclass
class SQLModel:
    table_annotation: str = None
    table_name: str = None
    table_verbose_name: str = None
    table_args: str = None
    table_constraints: list[TableConstraintItem] = field(default_factory=list)
    index: list[TableIndexItem] = field(default_factory=list)
    columns: list[SQLItem] = field(default_factory=list)

    @property
    def table_constraints_segment(self) -> str:
        items = []
        for item in self.table_constraints:
            cols = (f'"{c}"' for c in item.cols)
            items.append(f'{item.type}({", ".join(cols)}, name="{item.name}"),')
        
        segment = f"\n".join(items)
        segment = textwrap.indent(segment, prefix=' ' * 8)
        if segment and self.has_table_args:
            segment += "\n"
        return segment
    
    @property
    def table_index_segment(self) -> str:
        items = []
        for item in self.index:
            cols = [f'"{col}"' for col in item.cols]
            items.append(f'Index("{item.name}", {", ".join(cols)}),')

        segment = f"\n".join(items)
        segment = textwrap.indent(segment, prefix=' ' * 8)
        
        return segment
    
    @property
    def table_column_segment(self) -> str:
        string = ""
        for column in self.columns:
            # define column 
            col_def = f"    {column.name} = Column({column.type}"
            if column.is_primary:
                col_def += ", primary_key=True"
            if not column.is_nullable:
                col_def += ", nullable=False"
            if column.default is not None:
                col_def += f", default={column.default}"
            if column.is_unique:
                col_def += ", unique=True"
            if column.comment:
                col_def += f', comment="{column.comment}"'
            col_def += ")"

            string += f"{col_def}\n"
        return string
    
    @property
    def has_table_args(self):
        return any([self.table_constraints, self.index])

    def combine(self) -> str:
        table_cls = ''.join(word.capitalize() for word in self.table_name.split('_'))
        cls_def = f"class {table_cls}(BaseMixin):\n"

        # define annotation
        cls_def += f'    """{self.table_annotation or self.table_name}"""\n\n'

        # define __tablename__
        if self.table_verbose_name:
            cls_def += f"    \"\"\"{self.table_verbose_name}\"\"\""
        cls_def += f"""    __tablename__ = \"{self.table_name.lower()}\"\n"""
        
        # define __table_args__, include constraint and index
        if self.has_table_args:
            cls_def += f"    __table_args__ = (\n{self.table_constraints_segment}{self.table_index_segment}\n    )\n\n"
        else:
            cls_def += "\n"
        

        cls_def += self.table_column_segment

        return cls_def


class SQLToSQLAlchemyConverter(QMainWindow):
    def __init__(self):
        super().__init__()

        self.db_dialects = [
            {"label": "Postgres", "value": "postgres"},
            {"label": "MySQL", "value": "mysql"},
            {"label": "SQLite", "value": "sqlite"}
        ]
        self.cur_dialect = None

        self.init_ui()
        self.connect_signals()
        
        

    def init_ui(self):
        self.setWindowTitle("SQL Model Converter")
        self.setGeometry(100, 100, 800, 600)

        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()

        # Set the window to 80% of the screen size
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))

        # main widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.setStyleSheet("""
            QLabel {
                color: #D6D6D6;
                font-size: 14px;
            }
            QMessageBox {
                background-color: #1c1c1c;
                font-size: 14px;
            }
            QPushButton {
                height: 25px;
                border-radius: 5px;
                padding: 5px;
                background-color: #333333;
                color: #D6D6D6;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2E8B57;
            }
            QComboBox {
                height: 25px;
                padding: 5px;
                border-radius: 5px;
                font-size: 14px;
                color: #000000;
            } 
            QComboBox QAbstractItemView {
                margin: 0px;
                padding: 0px;
                border-radius: 6px;
                selection-background-color: #4caf50;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                margin: 2px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #50C878;
                color: #333333;
                background-color: #ecf4f4;
            }

        """)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(214, 214, 214))
        palette.setColor(QPalette.ColorRole.Window, QColor(28, 28, 28))
        palette.setColor(QPalette.ColorRole.Button, QColor(46, 46, 46))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(214, 214, 214))
        
        

        self.setPalette(palette)

        # layout
        self.layout = QHBoxLayout()
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.central_widget.setLayout(self.layout)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)

        # input box
        self.input_label = QLabel("SQL Statement:")
        self.input_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.input_text = QTextEdit()
        self.input_text.document().setDocumentMargin(10)
        font_metrics = self.input_text.fontMetrics()
        space_width = font_metrics.horizontalAdvance(' ')
        self.input_text.setTabStopDistance(4 * space_width)  # 4个空格宽度
        self.input_text.setPlaceholderText("""paste your sql statement here...\n\nfor instance:\n (The text after '--' will be parsed as a comment)\n                          
 -- role 
CREATE TABLE IF NOT EXISTS "role" (
    id INT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    org_id INT NOT NULL,            -- org id
    name VARCHAR(50) NOT NULL,      -- role name
    parent_id INT,
    ctime INT NOT NULL DEFAULT (EXTRACT(epoch FROM CURRENT_TIMESTAMP))::integer,
    state SMALLINT NOT NULL DEFAULT 1,
    data_scope SMALLINT NOT NULL,
    delete_id INT NOT NULL DEFAULT -1,
    UNIQUE(org_id, name, state, delete_id),
    CONSTRAINT "uk_role_org_id_name" UNIQUE ("org_id", "name"),
);
CREATE INDEX "ix_role_parent_id_id_state" on role(org_id, state);""")
        
        self.input_text.setAcceptRichText(False)
        self.input_text.setStyleSheet("""
                    QTextEdit {
                        background-color: rgb(51, 51, 51);
                        color: rgb(214, 214, 214);
                        font-family: Consolas;
                        font-size: 14pt;
                     
                    }
                """)

        # output box (SQLAlchemy model)
        self.output_label = QLabel("Model:")
        self.output_text = QTextEdit()
        self.output_text.document().setDocumentMargin(10)
        self.output_text.setReadOnly(True)
        self.output_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.output_text.setStyleSheet("""
                            QTextEdit {
                                background-color: rgb(51, 51, 51);
                                color: rgb(214, 214, 214);
                                font-family: Consolas;
                                font-size: 14pt;
                             
                            }
                        """)

        # button
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 0, 0, 0)

        button_container = QWidget()
        button_container.setLayout(button_layout)
        button_container.setMaximumWidth(150)  # 设置最大宽度
        button_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.convert_btn = QPushButton("convert")
        self.convert_btn.clicked.connect(self.convert_sql)
        self.convert_btn.setFixedWidth(100)

        self.copy_btn = QPushButton("copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setFixedWidth(100)

        # dropdown menu
        self.combo_box = QComboBox()
        for i in self.db_dialects:
            self.combo_box.addItem(i["label"], i["value"])

        self.combo_box.setCurrentIndex(0)  # 设置默认选中
        self.combo_box.currentIndexChanged.connect(self.on_database_changed)


        button_layout.addStretch()
        button_layout.addWidget(self.combo_box)
        button_layout.addWidget(self.convert_btn)
        button_layout.addWidget(self.copy_btn)
        button_layout.addStretch()
        button_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
       

        # right -- result
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)


        left_layout.addWidget(self.input_label)
        left_layout.addWidget(self.input_text)
        right_layout.addWidget(self.output_label)
        right_layout.addWidget(self.output_text)


        left_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setContentsMargins(10, 10, 10, 10)
        self.layout.addLayout(left_layout, stretch=4)
        self.layout.addWidget(button_container, stretch=1)
        self.layout.addLayout(right_layout, stretch=4)
        self.setLayout(self.layout)

        self.input_text.setPlainText("")

    def connect_signals(self):
        """连接信号与槽"""
        self.input_text.textChanged.connect(self.handle_input_change)

    
    def highlight_python_output(self, text):
        if not text:
            text = self.output_text.toPlainText()
        if not text.strip():
            return
            
        try:
            html = highlight(
                text,
                PythonLexer(),
                HtmlFormatter(
                    noclasses=True,
                    style="material",
                    prestyles="margin: 0; padding: 5px; background-color: #333333;"
                )
            )
            self.output_text.setHtml(html)
        except Exception as e:
            print(f"Python高亮错误: {e}")

    def handle_input_change(self):
        """处理输入变化事件"""
        sql_code = self.input_text.toPlainText()
        if not sql_code.strip():
            self.output_text.clear()

    def on_database_changed(self, index):
        self.cur_dialect = self.db_dialects[index]["value"]

    def get_cols(self, expr, constraint_name=None) -> list:
        cols = [col.name for col in expr.find_all(exp.Column)]
        if not cols:
            columns = []
            if isinstance(expr, exp.Constraint) and isinstance(expr.this, exp.Identifier):
                constraint_name = expr.this.name

            for e in expr.walk():
                if isinstance(e, exp.Column):
                    columns.append(e.name)
                elif isinstance(e, exp.Identifier):
                    if constraint_name and e.name == constraint_name:
                        continue
                    elif isinstance(e, exp.Identifier) and expr.parent != e:
                        columns.append(e.name)
            return list(dict.fromkeys(columns))
        return cols
    
    def get_table_annotation(self, ddl: str) -> str | None:
        if not ddl:
            return
        
        line = ddl.splitlines()[0]
        if line.startswith("--"):
            result = re.search(r'--\s*(.+)', line)
            if not result:
                return
            return result.group(1).strip()
        
    def get_table_name(self, parsed):
        for expression in parsed.find_all(exp.Table):
            table_name = expression.name
            if table_name:
                return table_name
        return



    def convert_sql(self):
        """将 PostgreSQL DDL 转换为 SQLAlchemy 模型"""
        ddl = self.input_text.toPlainText().strip()
        if not ddl:
            QMessageBox.warning(self, "warning", "sql statement is empty!")
            return

        try:
            parsed_items = sqlglot.parse(ddl, dialect=self.cur_dialect)
            sql_model = SQLModel()
            table_indexes = []
            table_constraints = []

            table_name = None
            # parse table annotation
            table_annotation = self.get_table_annotation(ddl)
            sql_model.table_annotation = table_annotation

            for parsed in parsed_items:
                if not parsed or not isinstance(parsed, exp.Create):
                    raise ValueError("sql input text invalid!")

                 # parse table name
                if not table_name:
                    table_name = self.get_table_name(parsed)
                    sql_model.table_name = table_name

                if parsed.kind == "TABLE":
                    # parse column
                    for expr in parsed.find_all(exp.ColumnDef):
                        col_type = expr.find(exp.DataType)
                        if not col_type:
                            continue


                        # 转换类型
                        type_mapping = {
                            "ARRAY": "ARRAY",
                            "BIGINT": "BigInteger",
                            "INT8": "BigInteger",
                            "SMALLINT": "SmallInteger",
                            "INT2": "SmallInteger",
                            "INTEGER": "Integer",
                            "INT": "Integer",
                            "INT4": "Integer",
                            "VARCHAR": "String",
                            "CHAR": "String",
                            "TEXT": "String",
                            "BOOLEAN": "Boolean",
                            "BOOL": "Boolean",
                            "TIMESTAMP": "TIMESTAMP",
                            "TIMESTAMPTZ": "TIMESTAMPTZ",
                            "DATE": "Date",
                            "DATETIME": "DateTime",
                            "FLOAT": "Float",
                            "FLOAT8": "Float",
                            "DOUBLE": "Float",
                            "NUMERIC": "Numeric",
                            "DECIMAL": "Numeric",
                            "JSON": "JSON",
                            "JSONB": "JSONB",
                            "SERIAL": "Integer",
                            "BIGSERIAL": "BigInteger"
                        }

                        dtype = col_type.this.name

                        if dtype not in type_mapping:
                            raise ValueError(f"不支持的字段类型: {dtype}")

                        sqlalchemy_type = type_mapping.get(dtype)

                        comments = [i.strip() for i in expr.comments] if expr.comments else []
                        comment = ",".join(comments)

                        if col_type.expressions:
                            col_exp_this = col_type.expressions[0].this
                            if dtype in ("VARCHAR", "CHAR"):
                                sqlalchemy_type = f"String({col_exp_this})"
                            if dtype == "ARRAY":
                                inner_type = col_exp_this.name
                                sqlalchemy_type = f"ARRAY({type_mapping.get(inner_type, 'String')})"
        
                        sql_item = SQLItem(name=expr.name, type=sqlalchemy_type, comment=comment)

                        # handle column constraints
                        constraints = expr.args.get("constraints", [])

                        for constraint in constraints:
                            constraint_kind = constraint.kind
                            if isinstance(constraint_kind, exp.NotNullColumnConstraint):
                                sql_item.is_nullable = False
                            elif isinstance(constraint_kind, exp.PrimaryKeyColumnConstraint):
                                sql_item.is_primary = True
                            elif isinstance(constraint_kind, exp.UniqueColumnConstraint):
                                sql_item.is_unique = True
                            elif isinstance(constraint_kind, exp.DefaultColumnConstraint):
                                default_value = constraint_kind.this
                                if isinstance(default_value, (exp.Literal, exp.Boolean)):
                                    sql_item.default = default_value.this
                                elif isinstance(default_value, exp.Func):
                                    if default_value.name.upper() == "EXTRACT":
                                        sql_item.default = "time.time"
                                    elif default_value.key == "currenttimestamp":
                                        sql_item.default = "func.now()"
                                elif hasattr(default_value, "output_name") and default_value.output_name:
                                    if default_value.output_name == "unixepoch":
                                        sql_item.default = "time.time"
                            elif isinstance(constraint_kind, exp.CommentColumnConstraint):
                                sql_item.comment = constraint.this

                        sql_model.columns.append(sql_item)

                    # handle table constraint
                    uq_constraint_sets = set()
                    for expr in parsed.find_all(exp.Constraint, exp.UniqueColumnConstraint):
                        constraint_cols = self.get_cols(expr)
                        if not constraint_cols:
                            continue
                        if expr.args.get("primary_key"):
                            continue
                        
                        joined_cols = "#".join(constraint_cols)
                        if joined_cols in uq_constraint_sets:
                            continue

                        uq_constraint_sets.add(joined_cols)

                        if isinstance(expr.this, (exp.UniqueColumnConstraint, exp.Identifier)) or isinstance(expr, (exp.UniqueColumnConstraint, exp.Identifier)):
                            constraint_name = getattr(expr.this, "name", None)
                    
                        if expr.args.get("unique"):
                            constraint_name = expr.args.get("name")
                        
                        if not constraint_name:
                            constraint_name = f"uk_{'_'.join(constraint_cols)}"

                        uq_constraint_sets.add(constraint_name)
                        constraint_item = TableConstraintItem(type="UniqueConstraint", name=constraint_name, cols=constraint_cols)
                        table_constraints.append(constraint_item)
                    
                
                if parsed.kind == "INDEX":
                    for expr in parsed.find_all(exp.Create):
                        index = expr.this
                        if isinstance(index, exp.Index):
                            index_item = TableIndexItem(type="normal", name=index.name, cols=self.get_cols(expr))
                            table_indexes.append(index_item)
                
                    

            sql_model.table_constraints = table_constraints
            sql_model.index = table_indexes
            

            if sql_model:
                output = sql_model.combine()
                self.output_text.setPlainText(output)
                self.highlight_python_output(output)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "error", f"Parse Error:\n {str(e)}\n\n{type(e).__name__}: {e}")

    def copy_to_clipboard(self):
        text = self.output_text.toPlainText()
        if text:
            pyperclip.copy(text)
        else:
            QMessageBox.warning(self, "warning", "No content to copy!")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon("./sql_ico.png"))
    window = SQLToSQLAlchemyConverter()
    window.show()
    sys.exit(app.exec())
