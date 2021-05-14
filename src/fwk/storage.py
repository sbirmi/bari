from collections import (
    defaultdict,
    namedtuple,
)
import json
import sqlite3

from fwk.Trace import (
    Level,
    trace,
)

# -------------------------------------
# Storage cell types
class Field():
    typ = None
    def __init__(self, name, qualifier=None):
        self.name = name
        self.qualifier = qualifier
        assert self.typ, "Can't use Field directly. Must use a derived class which sets typ"

    def create_desc(self):
        desc = "%s %s" % (self.name, self.typ)
        if self.qualifier:
            desc += " " + self.qualifier
        return desc

    def encode(self, value): # pylint: disable=no-self-use
        """Encode how it'll be stored in storage"""
        return value

    def decode(self, value): # pylint: disable=no-self-use
        """Decode when read from storage"""
        return value

class Txt(Field):
    typ = "text"

class Int(Field):
    typ = "integer"

class Bool(Field):
    typ = "integer"

    def encode(self, value):
        return int(value)

    def decode(self, value):
        return bool(value)

class Json(Field):
    typ = "text"

    def encode(self, value):
        return json.dumps(value)

    def decode(self, value):
        return json.loads(value)

# -------------------------------------
# Storage table

class Table():
    fields = []
    def __init__(self, cursor):
        self.cursor = cursor
        self.name = self.__class__.__name__
        self.create()
        self.field_by_name = {field.name: field for field in self.fields}

    def execute(self, *cmd):
        trace(Level.db, "table", self.name, "query", cmd)
        return self.cursor.execute(*cmd)

    @property
    def row_type(self):
        if not hasattr(self, "type_"):
            setattr(self, "type_",
                    namedtuple(self.name + "Row",
                        [row.name for row in self.fields]))
        return getattr(self, "type_")

    def get(self, cols, where=None, group_by=None):
        # pylint: disable=unused-variable,possibly-unused-variable
        where = where or {}
        group_by = group_by or []
        values = []

        cols = ", ".join(cols)
        table = self.name
        cmd = "select {cols} from {table}"
        if where:
            where_unspec = " and ".join("%s = ?" % w for w in where)
            values = self.encoded_values(where)
            cmd += " where {where_unspec}"
        if group_by:
            group_by = ", ".join(group_by)
            cmd += " group by {group_by}"

        cmd += ";"

        self.execute(cmd.format(**locals()), values)
        # pylint: disable=not-callable
        if cols == "*":
            def deserialized_row(row):
                return self.row_type(*[field.decode(val) for field, val in zip(self.fields, row)])
            return [deserialized_row(row) for row in self.cursor.fetchall()]

        return self.cursor.fetchall()

    def create_cmd(self):
        # pylint: disable=unused-variable,possibly-unused-variable
        table = self.name
        name_attrs = ", ".join(field.create_desc() for field in self.fields)
        return ("""create table {table} ({name_attrs})""".format(**locals()),)

    def create(self):
        cmd_args = self.create_cmd()
        try:
            res = self.execute(*cmd_args)
        except sqlite3.OperationalError as _:
            return None
        print("Created table", self.name)
        return res

    def encoded_values(self, dic):
        return [self.field_by_name[k].encode(v) for k, v in dic.items()]

    def insert_cmd(self, **kwargs):
        # pylint: disable=unused-variable,possibly-unused-variable
        table = self.name
        cells = ", ".join(kwargs.keys())
        values = self.encoded_values(kwargs)
        values_unspec = ", ".join("?" for _ in range(len(kwargs)))
        cmd = "insert into {table} ({cells}) values ({values_unspec});".format(**locals())
        return (cmd, values)

    def insert(self, **kwargs):
        cmd_args = self.insert_cmd(**kwargs)
        return self.execute(*cmd_args)

    def update_cmd(self, values, where):
        # pylint: disable=unused-variable,possibly-unused-variable
        table = self.name
        ret_values = []
        where_unspec = None

        cols_unspec = ", ".join("%s = ?" % col for col in values)
        ret_values.extend(self.encoded_values(values))

        cmd = "update {table} set {cols_unspec}"
        if where:
            where_unspec = " and ".join("%s = ?" % col for col in where)
            ret_values.extend(self.encoded_values(where))
            cmd += " where {where_unspec};"
        else:
            cmd += ";"
        return (cmd.format(**locals()), ret_values)

    def update(self, values, where):
        """
        Arguments
        ---------
        where : dict
            Dictionary of clauses to add
        values : dict
            Dictionary of values to add
        """
        cmd_args = self.update_cmd(values, where)
        return self.execute(*cmd_args)
