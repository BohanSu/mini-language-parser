#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说明：
这是一个完整的语法分析器，能够识别Mini语言的各种语法结构。
整个程序分为三大部分：
1. 词法分析器（Lexer）：把源代码字符串切分成一个个Token（词法单元）
2. 语法分析器（Parser）：根据文法规则，检查Token序列是否符合语法
3. AST打印器（ASTPrinter）：把分析结果用树状结构打印出来

核心思想：
- 词法分析就像"分词"，把"intx=5;"切成["int", "x", "=", "5", ";"]
- 语法分析就像"造句"，检查这些词能不能组成合法的句子
- AST就是语法树，展示程序的结构

采用的方法：
递归下降分析法 - 这是最直观的语法分析方法，为每个文法规则写一个函数，
函数之间相互调用，自然形成递归。比如：
  - parse_expr() 调用 parse_logic_or()
  - parse_logic_or() 调用 parse_logic_and()
  - ...一层层往下，最后到 parse_factor()

文法定义（非左递归版本）：
文法先消除了左递归，这样才能用递归下降法。
例如原来的 Expr -> Expr + Term 会导致无限递归，
改成 Expr -> Term ('+' Term)* 就可以了。

Program     -> StmtList                                    程序 = 一堆语句
StmtList    -> Stmt StmtList | ε                          语句列表 = 语句+语句列表 或空
Stmt        -> DeclStmt | AssignStmt | IfStmt | WhileStmt | BlockStmt   语句类型
DeclStmt    -> Type ID ('=' Expr)? ';'                     变量声明
AssignStmt  -> ID '=' Expr ';'                             赋值语句
IfStmt      -> 'if' Expr 'then' StmtList ('else' StmtList)? 'end'   if语句
WhileStmt   -> 'while' Expr 'do' StmtList 'end'            while循环
BlockStmt   -> 'begin' StmtList 'end'                      代码块
Expr        -> LogicOr                                      表达式从逻辑或开始
LogicOr     -> LogicAnd (('or'|'||') LogicAnd)*           逻辑或（优先级最低）
LogicAnd    -> LogicNot (('and'|'&&') LogicNot)*          逻辑与
LogicNot    -> ('not'|'!') LogicNot | Comparison           逻辑非
Comparison  -> ArithExpr (CompOp ArithExpr)?               比较运算
ArithExpr   -> Term (('+' | '-') Term)*                    加减运算
Term        -> Factor (('*' | '/') Factor)*                乘除运算（优先级高）
Factor      -> '(' Expr ')' | Number | ID | ...            最基本的元素
"""

import re
import sys
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional, Any, Tuple


# ==================== 第一部分：词法分析器 ====================
# 词法分析器的任务：把源代码字符串切分成Token（词法单元）
# 就像把句子切分成单词一样

class TokenType(Enum):
    """
    Token类型定义 - 定义所有可能的词法单元类型

    为什么要分这么多类型？
    因为语法分析时需要区分不同的Token，比如：
    - 关键字 if 和 标识符 if_count 要区分开
    - 运算符 = 和 == 要区分开
    """
    # 关键字 - 语言保留的特殊单词，不能作为变量名
    IF = auto()
    THEN = auto()
    ELSE = auto()
    END = auto()
    WHILE = auto()
    DO = auto()
    BEGIN = auto()
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    STRING = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()

    # 标识符和字面量 - 用户自己写的东西
    IDENTIFIER = auto()      # 变量名，如 x, count, my_var
    NUMBER = auto()          # 数字，如 42, 3.14
    STRING_LITERAL = auto()  # 字符串，如 "hello"

    # 运算符 - 各种计算符号
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    ASSIGN = auto()     # =   赋值
    EQ = auto()         # ==  相等判断
    NE = auto()         # !=  不等判断
    LT = auto()         # <
    GT = auto()         # >
    LE = auto()         # <=
    GE = auto()         # >=
    AND_OP = auto()     # &&  和 and 是同义词
    OR_OP = auto()      # ||  和 or 是同义词
    NOT_OP = auto()     # !   和 not 是同义词

    # 分隔符 - 用来分隔的符号
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    SEMICOLON = auto()  # ;   语句结束符
    COMMA = auto()      # ,

    # 特殊标记
    EOF = auto()        # End Of File，文件结束
    ERROR = auto()      # 错误Token


@dataclass
class Token:
    """
    Token（词法单元）- 词法分析的基本单位

    一个Token包含4个信息：
    1. type: 类型（是关键字？标识符？运算符？）
    2. value: 值（具体是什么，如变量名"x"，数字42）
    3. line: 行号（在源代码的第几行，方便报错定位）
    4. column: 列号（在那一行的第几列）

    例如：Token(IDENTIFIER, "x", line=1, col=5)
    表示第1行第5列有个标识符叫"x"
    """
    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)}, line={self.line}, col={self.column})"


class Lexer:
    """
    词法分析器 - 负责把源代码切分成Token序列

    工作流程：
    1. 从左到右扫描源代码字符串
    2. 跳过空格和注释
    3. 识别出每个Token（数字、标识符、运算符等）
    4. 记录每个Token的位置信息
    5. 最后返回Token列表

    举例：源代码 "int x = 5;"
    会被切分成：[Token(INT,"int"), Token(IDENTIFIER,"x"), Token(ASSIGN,"="),
                 Token(NUMBER,5), Token(SEMICOLON,";")]
    """

    # 关键字映射表 - 把关键字字符串映射到对应的TokenType
    # 为什么需要这个？因为 "if" 既可能是关键字，也可能是变量名的一部分
    # 所以读到标识符后要查表确认是不是关键字
    KEYWORDS = {
        'if': TokenType.IF,
        'then': TokenType.THEN,
        'else': TokenType.ELSE,
        'end': TokenType.END,
        'while': TokenType.WHILE,
        'do': TokenType.DO,
        'begin': TokenType.BEGIN,
        'int': TokenType.INT,
        'float': TokenType.FLOAT,
        'bool': TokenType.BOOL,
        'string': TokenType.STRING,
        'and': TokenType.AND,
        'or': TokenType.OR,
        'not': TokenType.NOT,
        'true': TokenType.TRUE,
        'false': TokenType.FALSE,
    }

    def __init__(self, source: str):
        """
        初始化词法分析器

        参数：
        - source: 源代码字符串

        内部状态：
        - pos: 当前读到第几个字符（位置指针）
        - line: 当前在第几行
        - column: 当前在第几列
        - tokens: 收集到的Token列表
        """
        self.source = source
        self.pos = 0          # 从第0个字符开始读
        self.line = 1         # 从第1行开始
        self.column = 1       # 从第1列开始
        self.tokens: List[Token] = []  # 空的Token列表

    def error(self, message: str):
        """报告词法错误，带上当前位置"""
        raise SyntaxError(f"词法错误 (行 {self.line}, 列 {self.column}): {message}")

    def peek(self, offset: int = 0) -> str:
        """
        查看当前位置（或向前offset个位置）的字符，但不移动位置指针

        为什么需要peek？
        有时候我需要"向前看"才能决定当前是什么Token
        比如看到'='，要再看一下下一个是不是'='，才能确定是'='还是'=='

        返回：字符，如果到了文件末尾返回'\0'
        """
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return '\0'  # 用 \0 表示文件结束

    def advance(self) -> str:
        """
        读取当前字符，并把位置指针向前移动一位

        同时更新行号和列号：
        - 如果读到换行符\n，行号+1，列号归1
        - 否则列号+1

        返回：当前字符
        """
        ch = self.peek()
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def skip_whitespace(self):
        """跳过空白字符（空格、制表符、换行符等）"""
        while self.peek().isspace():
            self.advance()

    def skip_comment(self):
        """
        跳过单行注释

        Mini语言的注释格式：// 开头，到行尾结束

        处理方式：
        1. 看当前和下一个字符是不是 '//'
        2. 如果是，一直读到换行符或文件结束
        3. 返回True表示跳过了注释，False表示不是注释
        """
        if self.peek() == '/' and self.peek(1) == '/':
            # 找到注释，一直读到行尾
            while self.peek() != '\n' and self.peek() != '\0':
                self.advance()
            return True
        return False

    def read_number(self) -> Token:
        """
        读取数字字面量

        支持两种格式：
        1. 整数：42, 100
        2. 浮点数：3.14, 0.5

        读取策略：
        1. 先读所有连续的数字字符
        2. 如果遇到小数点，且后面还有数字，继续读（浮点数）
        3. 否则就是整数

        注意：要记录Token开始的位置（不是结束位置）
        """
        start_line, start_col = self.line, self.column
        num_str = ""

        # 读整数部分
        while self.peek().isdigit():
            num_str += self.advance()

        # 检查小数点
        if self.peek() == '.' and self.peek(1).isdigit():
            num_str += self.advance()  # 读入 '.'
            # 读小数部分
            while self.peek().isdigit():
                num_str += self.advance()
            # 返回浮点数Token
            return Token(TokenType.NUMBER, float(num_str), start_line, start_col)

        # 返回整数Token
        return Token(TokenType.NUMBER, int(num_str), start_line, start_col)

    def read_identifier(self) -> Token:
        """
        读取标识符或关键字

        标识符规则：以字母或下划线开头，后面可以跟字母、数字、下划线
        例如：x, count, my_var, _temp, var123

        读取策略：
        1. 一直读字母、数字、下划线
        2. 读完后查关键字表，看是不是关键字
        3. 如果是关键字，返回关键字类型的Token
        4. 否则返回标识符类型的Token

        为什么要这样？因为 "if" 和 "if_count" 开头都一样，
        只有读完整个词才能判断是关键字还是标识符
        """
        start_line, start_col = self.line, self.column
        id_str = ""

        # 读标识符的所有字符
        while self.peek().isalnum() or self.peek() == '_':
            id_str += self.advance()

        # 检查是否是关键字（不区分大小写）
        token_type = self.KEYWORDS.get(id_str.lower(), TokenType.IDENTIFIER)
        return Token(token_type, id_str, start_line, start_col)

    def read_string(self) -> Token:
        """
        读取字符串字面量

        字符串规则：
        1. 用单引号或双引号包围
        2. 支持转义字符：\n（换行）、\t（制表符）、\\（反斜杠）、\"或\'（引号本身）

        读取策略：
        1. 记住开始的引号（'或"）
        2. 一直读到匹配的结束引号
        3. 遇到\时处理转义
        4. 如果到文件结束还没找到结束引号，报错

        例如："Hello\nWorld" 会被读成 Hello换行World
        """
        start_line, start_col = self.line, self.column
        quote = self.advance()  # 读掉开始引号（'或"）
        string_val = ""

        while self.peek() != quote and self.peek() != '\0':
            if self.peek() == '\\':
                # 转义字符处理
                self.advance()  # 跳过 \
                escape_char = self.advance()  # 读转义字符
                # 根据转义字符决定实际字符
                if escape_char == 'n':
                    string_val += '\n'
                elif escape_char == 't':
                    string_val += '\t'
                elif escape_char == '\\':
                    string_val += '\\'
                elif escape_char == quote:
                    string_val += quote
                else:
                    string_val += escape_char
            else:
                # 普通字符直接添加
                string_val += self.advance()

        # 检查是否正常结束
        if self.peek() == '\0':
            self.error("字符串未闭合")

        self.advance()  # 读掉结束引号
        return Token(TokenType.STRING_LITERAL, string_val, start_line, start_col)

    def tokenize(self) -> List[Token]:
        """
        主函数：把整个源代码切分成Token序列

        工作流程：
        1. 循环扫描源代码
        2. 每次循环：
           a. 跳过空白和注释
           b. 根据当前字符判断Token类型
           c. 调用对应的read_xxx函数读取Token
           d. 把Token加入列表
        3. 最后加一个EOF标记表示结束
        4. 返回Token列表

        难点：如何判断当前字符是什么Token的开始？
        - 数字开头 -> 数字字面量
        - 字母或下划线开头 -> 标识符或关键字
        - 引号开头 -> 字符串
        - = 开头 -> 可能是 = 或 ==（要看下一个）
        - 其他符号 -> 对应的运算符或分隔符
        """
        while self.pos < len(self.source):
            # 跳过空白
            self.skip_whitespace()

            if self.pos >= len(self.source):
                break

            # 跳过注释
            if self.skip_comment():
                continue

            # 记录当前Token的起始位置
            start_line, start_col = self.line, self.column
            ch = self.peek()

            # 根据首字符判断Token类型
            if ch.isdigit():
                # 数字开头 -> 数字字面量
                self.tokens.append(self.read_number())

            elif ch.isalpha() or ch == '_':
                # 字母或下划线开头 -> 标识符或关键字
                self.tokens.append(self.read_identifier())

            elif ch in ('"', "'"):
                # 引号开头 -> 字符串
                self.tokens.append(self.read_string())

            # 下面处理双字符运算符（需要向前看一位）
            elif ch == '=' and self.peek(1) == '=':
                # == 相等判断
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.EQ, '==', start_line, start_col))

            elif ch == '!' and self.peek(1) == '=':
                # != 不等判断
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.NE, '!=', start_line, start_col))

            elif ch == '<' and self.peek(1) == '=':
                # <= 小于等于
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LE, '<=', start_line, start_col))

            elif ch == '>' and self.peek(1) == '=':
                # >= 大于等于
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.GE, '>=', start_line, start_col))

            elif ch == '&' and self.peek(1) == '&':
                # && 逻辑与
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.AND_OP, '&&', start_line, start_col))

            elif ch == '|' and self.peek(1) == '|':
                # || 逻辑或
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.OR_OP, '||', start_line, start_col))

            # 下面处理单字符运算符和分隔符
            elif ch == '+':
                self.advance()
                self.tokens.append(Token(TokenType.PLUS, '+', start_line, start_col))
            elif ch == '-':
                self.advance()
                self.tokens.append(Token(TokenType.MINUS, '-', start_line, start_col))
            elif ch == '*':
                self.advance()
                self.tokens.append(Token(TokenType.STAR, '*', start_line, start_col))
            elif ch == '/':
                self.advance()
                self.tokens.append(Token(TokenType.SLASH, '/', start_line, start_col))
            elif ch == '=':
                self.advance()
                self.tokens.append(Token(TokenType.ASSIGN, '=', start_line, start_col))
            elif ch == '<':
                self.advance()
                self.tokens.append(Token(TokenType.LT, '<', start_line, start_col))
            elif ch == '>':
                self.advance()
                self.tokens.append(Token(TokenType.GT, '>', start_line, start_col))
            elif ch == '!':
                self.advance()
                self.tokens.append(Token(TokenType.NOT_OP, '!', start_line, start_col))
            elif ch == '(':
                self.advance()
                self.tokens.append(Token(TokenType.LPAREN, '(', start_line, start_col))
            elif ch == ')':
                self.advance()
                self.tokens.append(Token(TokenType.RPAREN, ')', start_line, start_col))
            elif ch == ';':
                self.advance()
                self.tokens.append(Token(TokenType.SEMICOLON, ';', start_line, start_col))
            elif ch == ',':
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ',', start_line, start_col))
            elif ch == '\0':
                break
            else:
                # 遇到不认识的字符，报错
                self.error(f"非法字符 '{ch}'")

        # 最后加上EOF标记
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens


# ==================== 第二部分：抽象语法树（AST）节点定义 ====================
# AST是语法分析的结果，用树状结构表示程序的语法结构
# 每种语法结构对应一种AST节点

from dataclasses import field

class ASTNode:
    """AST节点基类 - 所有AST节点都继承这个类"""
    pass


@dataclass
class Program(ASTNode):
    """
    程序节点 - AST的根节点

    一个程序就是一堆语句的集合
    例如：
        int x = 5;
        x = x + 1;

    对应的AST：
        Program
        ├─ DeclStmt (int x = 5)
        └─ AssignStmt (x = x + 1)
    """
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class NumberLiteral(ASTNode):
    """
    数字字面量节点

    例如：42, 3.14
    """
    value: float = 0
    line: int = 0
    column: int = 0


@dataclass
class StringLiteral(ASTNode):
    """
    字符串字面量节点

    例如："Hello World"
    """
    value: str = ""
    line: int = 0
    column: int = 0


@dataclass
class BoolLiteral(ASTNode):
    """
    布尔字面量节点

    例如：true, false
    """
    value: bool = False
    line: int = 0
    column: int = 0


@dataclass
class Identifier(ASTNode):
    """
    标识符节点 - 表示变量名

    例如：x, count, my_var
    """
    name: str = ""
    line: int = 0
    column: int = 0


@dataclass
class BinaryOp(ASTNode):
    """
    二元运算节点 - 两个操作数的运算

    例如：x + y, a * b, flag and true

    结构：
        BinaryOp(op='+')
        ├─ left: x
        └─ right: y
    """
    op: str = ""                      # 运算符：+, -, *, /, and, or等
    left: Optional[ASTNode] = None    # 左操作数
    right: Optional[ASTNode] = None   # 右操作数
    line: int = 0
    column: int = 0


@dataclass
class UnaryOp(ASTNode):
    """
    一元运算节点 - 只有一个操作数的运算

    例如：-5, !flag, not true

    结构：
        UnaryOp(op='not')
        └─ operand: flag
    """
    op: str = ""                      # 运算符：-, +, not, !
    operand: Optional[ASTNode] = None # 操作数
    line: int = 0
    column: int = 0


@dataclass
class AssignStmt(ASTNode):
    """
    赋值语句节点

    例如：x = 5 + 3;

    结构：
        AssignStmt(name='x')
        └─ value: BinaryOp(+)
            ├─ 5
            └─ 3
    """
    name: str = ""                    # 变量名
    value: Optional[ASTNode] = None   # 赋的值（右边的表达式）
    line: int = 0
    column: int = 0


@dataclass
class DeclStmt(ASTNode):
    """
    变量声明语句节点

    例如：int x;  或  int x = 5;

    结构：
        DeclStmt(type='int', name='x')
        └─ init_value: 5  (可选)
    """
    var_type: str = ""                     # 变量类型：int, float, bool, string
    name: str = ""                         # 变量名
    init_value: Optional[ASTNode] = None   # 初始值（可以没有）
    line: int = 0
    column: int = 0


@dataclass
class IfStmt(ASTNode):
    """
    if语句节点

    例如：
        if x > 0 then
            y = 1;
        else
            y = 0;
        end

    结构：
        IfStmt
        ├─ condition: x > 0
        ├─ then_branch: [y = 1;]
        └─ else_branch: [y = 0;]  (可选)
    """
    condition: Optional[ASTNode] = None           # 条件表达式
    then_branch: List[ASTNode] = field(default_factory=list)  # then分支的语句列表
    else_branch: Optional[List[ASTNode]] = None   # else分支的语句列表（可选）
    line: int = 0
    column: int = 0


@dataclass
class WhileStmt(ASTNode):
    """
    while循环节点

    例如：
        while i < 10 do
            i = i + 1;
        end

    结构：
        WhileStmt
        ├─ condition: i < 10
        └─ body: [i = i + 1;]
    """
    condition: Optional[ASTNode] = None           # 循环条件
    body: List[ASTNode] = field(default_factory=list)  # 循环体语句列表
    line: int = 0
    column: int = 0


@dataclass
class BlockStmt(ASTNode):
    """
    代码块节点

    例如：
        begin
            int x = 5;
            x = x + 1;
        end

    结构：
        BlockStmt
        └─ statements: [int x = 5;, x = x + 1;]
    """
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 0
    column: int = 0


# ==================== 第三部分：语法分析器 ====================
# 语法分析器的任务：检查Token序列是否符合文法规则，并构建AST

class SymbolTable:
    """
    符号表：用于存储变量声明信息，检查语义错误
    支持嵌套作用域（链式结构）
    """
    def __init__(self, parent=None):
        self.symbols = {}  # name -> type
        self.parent = parent  # 父作用域

    def define(self, name, type_name):
        """定义变量"""
        self.symbols[name] = type_name

    def resolve(self, name):
        """查找变量定义（从当前作用域向上查找）"""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None

    def defined_locally(self, name):
        """检查当前作用域是否已定义"""
        return name in self.symbols


class Parser:
    """
    递归下降语法分析器

    核心思想：
    为每个文法规则写一个函数，函数名通常是 parse_XXX
    这些函数相互调用，形成递归结构

    例如文法规则：
        Expr -> Term (('+' | '-') Term)*
    对应函数：
        def parse_expr(self):
            left = self.parse_term()  # 先解析一个Term
            while 当前是+或-:
                op = 读取运算符
                right = self.parse_term()  # 再解析一个Term
                left = 合并成二元运算  # left = left + right
            return left

    关键概念：
    1. 当前Token (current): 正在分析的Token
    2. 向前看 (peek): 偷看下一个Token，但不移动位置
    3. 消耗 (advance): 读取当前Token并移动到下一个
    4. 期望 (expect): 检查当前Token是否是期望的类型，是就消耗，否则报错

    错误处理：
    使用"恐慌模式"(Panic Mode)恢复
    - 发现错误时，跳过一些Token直到找到"同步点"（如分号、关键字）
    - 然后继续分析，这样可以一次找出多个错误
    """

    def __init__(self, tokens: List[Token]):
        """
        初始化语法分析器

        参数：
        - tokens: 词法分析器生成的Token列表

        内部状态：
        - pos: 当前分析到第几个Token
        - errors: 收集到的错误信息列表
        """
        self.tokens = tokens
        self.pos = 0
        self.errors: List[str] = []
        self.current_scope = SymbolTable()  # 全局作用域

    def enter_scope(self):
        """进入新作用域"""
        self.current_scope = SymbolTable(self.current_scope)

    def exit_scope(self):
        """退出当前作用域"""
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def current(self) -> Token:
        """获取当前Token（正在分析的Token）"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # 如果越界，返回EOF

    def peek(self, offset: int = 0) -> Token:
        """
        向前看offset个Token，但不移动位置

        为什么需要peek？
        有时候要看下一个Token才能决定当前怎么分析
        比如：看到标识符x，要看下一个是不是=，才能确定是赋值语句还是表达式
        """
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        """
        消耗当前Token，移动到下一个

        返回：被消耗的Token
        """
        token = self.current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def match(self, *types: TokenType) -> bool:
        """
        检查当前Token是否匹配给定的类型之一

        例如：match(TokenType.PLUS, TokenType.MINUS)
        检查当前Token是不是 + 或 -

        返回：True表示匹配，False表示不匹配
        """
        return self.current().type in types

    def expect(self, token_type: TokenType, message: str) -> Token:
        """
        期望当前Token是某个类型

        如果是：消耗它并返回
        如果不是：报错

        这是递归下降分析法的核心操作
        例如：解析if语句时，expect(THEN, "预期'then'")
        确保if和条件表达式后面一定要跟then关键字
        """
        if self.current().type == token_type:
            return self.advance()
        # 不匹配，报错
        self.error(message)
        return self.current()

    def error(self, message: str):
        """
        报告语法错误

        会记录错误位置和信息，然后抛出异常
        外层会捕获异常，调用synchronize进行错误恢复
        """
        token = self.current()
        # 构造详细的错误信息
        error_msg = f"语法错误 (行 {token.line}, 列 {token.column}): {message}"

        # 添加当前token的信息，帮助理解错误
        if token.type != TokenType.EOF:
            error_msg += f"\n  当前token: {token.type.name} '{token.value}'"
        else:
            error_msg += f"\n  当前token: 文件结束(EOF)"

        self.errors.append(error_msg)
        raise SyntaxError(error_msg)

    def synchronize(self):
        """
        错误恢复 - 恐慌模式

        当遇到语法错误时，我不能直接停止，否则只能报告第一个错误
        要尽量继续分析，找出更多错误

        恢复策略：
        1. 跳过当前Token
        2. 一直跳，直到找到"同步点"：
           - 语句结束符 ; 后面
           - 新语句开始的关键字（if, while, int等）
           - 块结束标记（end, else）
        3. 从同步点继续分析

        为什么这样可以？
        因为语句之间相对独立，一个语句错了不影响下一个语句
        到下一个语句开始的地方，可以重新开始分析
        """
        self.advance()
        while not self.match(TokenType.EOF):
            # 如果前一个Token是分号，说明到了语句边界
            if self.peek(-1).type == TokenType.SEMICOLON:
                return
            # 如果当前Token是语句开始的关键字，也是同步点
            if self.match(TokenType.IF, TokenType.WHILE, TokenType.BEGIN,
                         TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.STRING):
                return
            # 如果当前Token是块结束标记，也是同步点（重要！防止在if/while中死循环）
            if self.match(TokenType.END, TokenType.ELSE):
                return
            self.advance()

    # ========== 语法分析方法 - 每个文法规则对应一个方法 ==========

    def parse(self) -> Program:
        """
        程序的入口函数

        文法规则：Program -> StmtList

        步骤：
        1. 解析语句列表
        2. 检查是否到了文件结束
        3. 如果解析过程中收集到了错误，抛出异常
        4. 返回Program节点
        """
        statements = self.parse_stmt_list()
        if not self.match(TokenType.EOF):
            self.error(f"预期文件结束，但发现 '{self.current().value}'")

        # 如果在解析过程中收集到了错误，抛出异常
        # 这样测试框架可以检测到语法错误
        if self.errors:
            error_summary = f"发现 {len(self.errors)} 个语法错误"
            raise SyntaxError(error_summary)

        return Program(statements=statements, line=1, column=1)

    def parse_stmt_list(self, end_tokens: Tuple[TokenType, ...] = (TokenType.EOF,)) -> List[ASTNode]:
        """
        解析语句列表

        文法规则：StmtList -> Stmt StmtList | ε
        翻译：语句列表 = 一个语句 + 语句列表，或者什么都没有（空）

        实现：
        循环解析语句，直到遇到结束标记（如EOF、end、else）

        参数：
        - end_tokens: 结束标记的集合（不同上下文有不同的结束标记）
          比如：
          - 程序级别：EOF
          - if语句的then分支：ELSE或END
          - while循环体：END

        错误处理：
        如果解析某个语句出错，调用synchronize恢复，继续解析下一个语句

        防止无限循环：
        即使在等待特定结束标记（如END），也要检查EOF，避免文件提前结束时死循环
        """
        statements = []
        prev_pos = -1
        while not self.match(*end_tokens):
            # 防止无限循环：如果位置没有变化，说明卡住了
            if self.pos == prev_pos:
                self.error(f"无法继续解析，当前token: {self.current()}")
                break
            prev_pos = self.pos

            # 防止无限循环：如果到了文件结尾但还没找到期望的结束标记，退出
            # 这种情况会在后面的expect调用中报错
            if self.match(TokenType.EOF) and TokenType.EOF not in end_tokens:
                break

            try:
                stmt = self.parse_stmt()
                if stmt:
                    statements.append(stmt)
            except SyntaxError:
                # 出错了，恢复后继续
                self.synchronize()
        return statements

    def parse_stmt(self) -> Optional[ASTNode]:
        """
        解析单条语句

        文法规则：Stmt -> DeclStmt | AssignStmt | IfStmt | WhileStmt | BlockStmt | Expr ';'
        翻译：语句可以是变量声明、赋值、if、while、代码块，或者表达式语句

        实现思路：
        根据当前Token的类型，判断是哪种语句，然后调用对应的解析函数

        判断方法（向前看1-2个Token）：
        - int/float/bool/string开头 -> 变量声明
        - if开头 -> if语句
        - while开头 -> while语句
        - begin开头 -> 代码块
        - 标识符+等号 -> 赋值语句
        - 其他 -> 表达式语句
        """
        # 变量声明：以类型关键字开头
        if self.match(TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.STRING):
            return self.parse_decl_stmt()

        # if语句
        if self.match(TokenType.IF):
            return self.parse_if_stmt()

        # while语句
        if self.match(TokenType.WHILE):
            return self.parse_while_stmt()

        # begin...end代码块
        if self.match(TokenType.BEGIN):
            return self.parse_block_stmt()

        # 赋值语句：标识符后面跟等号
        if self.match(TokenType.IDENTIFIER):
            if self.peek(1).type == TokenType.ASSIGN:
                return self.parse_assign_stmt()
            # 标识符但不是赋值，报错（不允许单独的表达式语句）
            else:
                self.error(f"非法语句: 标识符 '{self.current().value}' 后应跟 '=' 进行赋值")

        # 不允许单独的表达式语句
        # Mini语言只允许：变量声明、赋值、if、while、begin...end
        if not self.match(TokenType.EOF, TokenType.END, TokenType.ELSE, TokenType.SEMICOLON):
            self.error(f"非法语句: 预期变量声明、赋值、if、while或begin，但发现 '{self.current().value}'")

        return None

    def parse_decl_stmt(self) -> DeclStmt:
        """
        解析变量声明语句

        文法规则：DeclStmt -> Type ID ('=' Expr)? ';'
        翻译：类型 变量名 [可选的初始化] 分号

        例如：
        - int x;           -> 声明整型变量x，不初始化
        - int x = 5;       -> 声明整型变量x，初始化为5
        - float pi = 3.14; -> 声明浮点变量pi，初始化为3.14

        实现步骤：
        1. 读取类型关键字（已经确定是类型了）
        2. 期望一个标识符（变量名）
        3. 检查是否有等号，如果有，解析初始化表达式
        4. 期望分号
        5. 返回DeclStmt节点
        """
        type_token = self.advance()  # 读取类型（int/float/bool/string）
        var_type = type_token.value
        line, col = type_token.line, type_token.column

        # 期望变量名
        name_token = self.expect(TokenType.IDENTIFIER, "预期变量名")
        name = name_token.value

        # 语义检查：变量重复声明
        if self.current_scope.defined_locally(name):
            self.error(f"语义错误: 变量 '{name}' 重复声明")
        else:
            self.current_scope.define(name, var_type)

        # 检查是否有初始化
        init_value = None
        if self.match(TokenType.ASSIGN):
            self.advance()  # 消耗 =
            init_value = self.parse_expr()  # 解析初始化表达式

        # 期望分号
        self.expect(TokenType.SEMICOLON, "预期 ';'")

        return DeclStmt(var_type=var_type, name=name, init_value=init_value, line=line, column=col)

    def parse_assign_stmt(self) -> AssignStmt:
        """
        解析赋值语句

        文法规则：AssignStmt -> ID '=' Expr ';'
        翻译：变量名 等号 表达式 分号

        例如：x = 5 + 3;

        实现步骤：
        1. 读取变量名（已经确定是标识符了）
        2. 期望等号
        3. 解析右边的表达式
        4. 期望分号
        5. 返回AssignStmt节点
        """
        name_token = self.advance()  # 读取变量名
        line, col = name_token.line, name_token.column

        # 语义检查：变量未声明
        if not self.current_scope.resolve(name_token.value):
            self.error(f"语义错误: 变量 '{name_token.value}' 未声明即使用")

        self.expect(TokenType.ASSIGN, "预期 '='")  # 期望 =
        value = self.parse_expr()  # 解析右边的表达式
        self.expect(TokenType.SEMICOLON, "预期 ';'")  # 期望 ;

        return AssignStmt(name=name_token.value, value=value, line=line, column=col)

    def parse_if_stmt(self) -> IfStmt:
        """
        解析if语句

        文法规则：IfStmt -> 'if' Expr 'then' StmtList ('else' StmtList)? 'end'
        翻译：if 条件 then 语句列表 [可选的else分支] end

        例如：
        if x > 0 then
            y = 1;
        else
            y = 0;
        end

        实现步骤：
        1. 消耗 if 关键字
        2. 解析条件表达式
        3. 期望 then
        4. 解析then分支的语句列表（直到遇到else或end）
        5. 如果有else，解析else分支的语句列表（直到end）
        6. 期望 end
        7. 返回IfStmt节点

        难点：如何知道then分支在哪里结束？
        答：传递结束标记(ELSE, END)给parse_stmt_list
        """
        if_token = self.advance()  # 消耗 'if'
        line, col = if_token.line, if_token.column

        condition = self.parse_expr()  # 解析条件表达式
        self.expect(TokenType.THEN, "预期 'then'")  # 期望 then

        # 解析then分支，遇到else或end停止
        self.enter_scope()
        then_branch = self.parse_stmt_list((TokenType.ELSE, TokenType.END))
        self.exit_scope()

        # 检查是否有else分支
        else_branch = None
        if self.match(TokenType.ELSE):
            self.advance()  # 消耗 else
            # 解析else分支，遇到end停止
            self.enter_scope()
            else_branch = self.parse_stmt_list((TokenType.END,))
            self.exit_scope()

        self.expect(TokenType.END, "预期 'end'")  # 期望 end

        return IfStmt(condition=condition, then_branch=then_branch,
                     else_branch=else_branch, line=line, column=col)

    def parse_while_stmt(self) -> WhileStmt:
        """
        解析while循环

        文法规则：WhileStmt -> 'while' Expr 'do' StmtList 'end'
        翻译：while 条件 do 语句列表 end

        例如：
        while i < 10 do
            i = i + 1;
        end

        实现步骤：
        1. 消耗 while
        2. 解析条件表达式
        3. 期望 do
        4. 解析循环体语句列表（直到end）
        5. 期望 end
        6. 返回WhileStmt节点
        """
        while_token = self.advance()  # 消耗 'while'
        line, col = while_token.line, while_token.column

        condition = self.parse_expr()  # 解析条件
        self.expect(TokenType.DO, "预期 'do'")  # 期望 do

        # 解析循环体，遇到end停止
        self.enter_scope()
        body = self.parse_stmt_list((TokenType.END,))
        self.exit_scope()

        self.expect(TokenType.END, "预期 'end'")  # 期望 end

        return WhileStmt(condition=condition, body=body, line=line, column=col)

    def parse_block_stmt(self) -> BlockStmt:
        """
        解析代码块

        文法规则：BlockStmt -> 'begin' StmtList 'end'
        翻译：begin 语句列表 end

        例如：
        begin
            int x = 5;
            x = x + 1;
        end

        实现步骤：
        1. 消耗 begin
        2. 解析语句列表（直到end）
        3. 期望 end
        4. 返回BlockStmt节点
        """
        begin_token = self.advance()  # 消耗 'begin'
        line, col = begin_token.line, begin_token.column

        self.enter_scope()  # 进入块作用域
        # 解析代码块内的语句，遇到end停止
        statements = self.parse_stmt_list((TokenType.END,))
        self.exit_scope()  # 退出块作用域

        self.expect(TokenType.END, "预期 'end'")  # 期望 end

        return BlockStmt(statements=statements, line=line, column=col)

    # ========== 表达式解析 - 按优先级从低到高 ==========
    #
    # 为什么要分这么多层？
    # 因为运算符有优先级！
    # - 逻辑或 or 优先级最低
    # - 逻辑与 and 次之
    # - 比较运算 <、> 再次之
    # - 加减运算 +、- 再次之
    # - 乘除运算 *、/ 优先级最高
    #
    # 优先级高的要放在递归的深层
    # 这样先计算优先级高的，再计算优先级低的
    #
    # 例如：a or b and c * d
    # 解析顺序：
    # 1. parse_logic_or 看到 or，左边是 a，右边继续
    # 2. parse_logic_and 看到 and，左边是 b，右边继续
    # 3. parse_term 看到 *，左边是 c，右边是 d
    # 4. 返回 c*d，返回 b and (c*d)，返回 a or (b and (c*d))
    #
    # 结果：先算乘法，再算and，最后算or，符合优先级！

    def parse_expr(self) -> ASTNode:
        """
        表达式入口

        文法规则：Expr -> LogicOr

        表达式从优先级最低的逻辑或开始解析
        """
        return self.parse_logic_or()

    def parse_logic_or(self) -> ASTNode:
        """
        解析逻辑或表达式（优先级最低）

        文法规则：LogicOr -> LogicAnd (('or' | '||') LogicAnd)*
        翻译：逻辑与 [or 逻辑与]*

        例如：a or b or c

        实现：
        1. 先解析一个LogicAnd
        2. 循环：如果看到or或||，继续解析下一个LogicAnd
        3. 把它们组合成二元运算节点

        为什么是循环不是递归？
        因为文法规则用了*（零次或多次），循环更直观
        而且避免了左递归（左递归会导致无限递归）

        组合方式（左结合）：
        a or b or c
        解析成：(a or b) or c
        不是：a or (b or c)
        """
        left = self.parse_logic_and()  # 先解析左边

        # 循环处理所有的or运算
        while self.match(TokenType.OR, TokenType.OR_OP):
            op_token = self.advance()  # 读取 or 或 ||
            right = self.parse_logic_and()  # 解析右边
            # 组合成二元运算节点
            left = BinaryOp(op=op_token.value, left=left, right=right,
                           line=op_token.line, column=op_token.column)

        return left

    def parse_logic_and(self) -> ASTNode:
        """
        解析逻辑与表达式

        文法规则：LogicAnd -> LogicNot (('and' | '&&') LogicNot)*

        例如：a and b and c -> (a and b) and c

        实现方式同parse_logic_or，只是运算符换成and/&&
        优先级比or高，所以在or的下一层
        """
        left = self.parse_logic_not()

        while self.match(TokenType.AND, TokenType.AND_OP):
            op_token = self.advance()
            right = self.parse_logic_not()
            left = BinaryOp(op=op_token.value, left=left, right=right,
                           line=op_token.line, column=op_token.column)

        return left

    def parse_logic_not(self) -> ASTNode:
        """
        解析逻辑非表达式

        文法规则：LogicNot -> ('not' | '!') LogicNot | Comparison
        翻译：not 逻辑非 或者 比较表达式

        例如：not not true, !flag

        特点：这是一元运算符，可以连续出现
        如 not not x 表示 not (not x)

        实现：
        1. 如果看到not或!，递归调用自己，处理连续的not
        2. 否则解析比较表达式
        """
        if self.match(TokenType.NOT, TokenType.NOT_OP):
            op_token = self.advance()  # 读取 not 或 !
            operand = self.parse_logic_not()  # 递归处理，支持 not not
            return UnaryOp(op=op_token.value, operand=operand,
                          line=op_token.line, column=op_token.column)

        # 不是not，继续解析比较表达式
        return self.parse_comparison()

    def parse_comparison(self) -> ASTNode:
        """
        解析比较表达式

        文法规则：Comparison -> ArithExpr (CompOp ArithExpr)?
        翻译：算术表达式 [比较运算符 算术表达式]?

        例如：x > 5, a == b, y <= 10

        注意：比较运算符不能连用
        a < b < c 是不合法的（和数学不一样）
        要写成 a < b and b < c

        实现：
        1. 先解析左边的算术表达式
        2. 如果有比较运算符，解析右边的算术表达式
        3. 组合成二元运算
        4. 如果没有比较运算符，直接返回算术表达式
        """
        left = self.parse_arith_expr()  # 先解析左边

        # 检查是否有比较运算符
        if self.match(TokenType.EQ, TokenType.NE, TokenType.LT,
                     TokenType.GT, TokenType.LE, TokenType.GE):
            op_token = self.advance()  # 读取比较运算符
            right = self.parse_arith_expr()  # 解析右边
            return BinaryOp(op=op_token.value, left=left, right=right,
                           line=op_token.line, column=op_token.column)

        # 没有比较运算符，直接返回
        return left

    def parse_arith_expr(self) -> ASTNode:
        """
        解析算术表达式（加减运算）

        文法规则：ArithExpr -> Term (('+' | '-') Term)*

        例如：1 + 2 - 3 + 4 -> ((1 + 2) - 3) + 4

        实现方式同parse_logic_or
        优先级比比较低，比乘除高
        """
        left = self.parse_term()

        while self.match(TokenType.PLUS, TokenType.MINUS):
            op_token = self.advance()
            right = self.parse_term()
            left = BinaryOp(op=op_token.value, left=left, right=right,
                           line=op_token.line, column=op_token.column)

        return left

    def parse_term(self) -> ASTNode:
        """
        解析项（乘除运算）

        文法规则：Term -> Factor (('*' | '/') Factor)*

        例如：2 * 3 / 4 * 5 -> ((2 * 3) / 4) * 5

        实现方式同parse_logic_or
        优先级最高（除了括号和字面量）
        """
        left = self.parse_factor()

        while self.match(TokenType.STAR, TokenType.SLASH):
            op_token = self.advance()
            right = self.parse_factor()
            left = BinaryOp(op=op_token.value, left=left, right=right,
                           line=op_token.line, column=op_token.column)

        return left

    def parse_factor(self) -> ASTNode:
        """
        解析因子（最基本的表达式元素）

        文法规则：Factor -> '(' Expr ')' | Number | String | Bool | ID | ('+'|'-') Factor

        因子包括：
        1. 括号表达式：(1 + 2)
        2. 数字字面量：42, 3.14
        3. 字符串字面量："hello"
        4. 布尔字面量：true, false
        5. 标识符：x, count
        6. 一元正负号：-5, +3

        这是递归的最底层，再往下就是Token本身了

        实现：
        根据当前Token类型，返回对应的AST节点
        """
        token = self.current()

        # 括号表达式：优先级最高，里面可以是任何表达式
        if self.match(TokenType.LPAREN):
            self.advance()  # 消耗 (
            expr = self.parse_expr()  # 递归解析表达式
            self.expect(TokenType.RPAREN, "预期 ')'")  # 期望 )
            return expr

        # 数字字面量
        if self.match(TokenType.NUMBER):
            self.advance()
            return NumberLiteral(value=token.value, line=token.line, column=token.column)

        # 字符串字面量
        if self.match(TokenType.STRING_LITERAL):
            self.advance()
            return StringLiteral(value=token.value, line=token.line, column=token.column)

        # 布尔字面量 true
        if self.match(TokenType.TRUE):
            self.advance()
            return BoolLiteral(value=True, line=token.line, column=token.column)

        # 布尔字面量 false
        if self.match(TokenType.FALSE):
            self.advance()
            return BoolLiteral(value=False, line=token.line, column=token.column)

        # 标识符（变量名）
        if self.match(TokenType.IDENTIFIER):
            self.advance()
            # 语义检查：变量未声明
            if not self.current_scope.resolve(token.value):
                self.error(f"语义错误: 变量 '{token.value}' 未声明即使用")
            return Identifier(name=token.value, line=token.line, column=token.column)

        # 一元正负号：+5, -3
        if self.match(TokenType.PLUS, TokenType.MINUS):
            op_token = self.advance()
            operand = self.parse_factor()  # 递归，支持 --5 这种
            return UnaryOp(op=op_token.value, operand=operand,
                          line=op_token.line, column=op_token.column)

        # 如果都不是，说明语法错误
        self.error(f"预期表达式，但发现 '{token.value}'")
        return NumberLiteral(value=0, line=token.line, column=token.column)


# ==================== 第四部分：AST打印器 ====================
# 把AST用树状结构打印出来，方便查看和调试

class ASTPrinter:
    """
    语法树打印器 - 把AST用缩进形式打印出来

    打印效果：
        Program
          Declaration: int x (with init)
            Number: 5
          Assignment: x =
            BinaryOp: +
              Identifier: x
              Number: 1

    实现：
    递归遍历AST的每个节点，根据节点类型打印信息
    用缩进表示层次关系
    """

    def __init__(self):
        self.indent = 0  # 当前缩进层级

    def print(self, node: ASTNode) -> str:
        """打印整棵树，返回字符串"""
        lines = []
        self._print_node(node, lines)
        return '\n'.join(lines)

    def _indent_str(self) -> str:
        """生成缩进字符串，每层两个空格"""
        return '  ' * self.indent

    def _print_node(self, node: ASTNode, lines: List[str]):
        """
        递归打印节点

        对每种AST节点类型，打印不同的信息
        然后递归打印子节点（增加缩进）
        """
        if isinstance(node, Program):
            lines.append(f"{self._indent_str()}Program")
            self.indent += 1
            for stmt in node.statements:
                self._print_node(stmt, lines)
            self.indent -= 1

        elif isinstance(node, NumberLiteral):
            lines.append(f"{self._indent_str()}Number: {node.value}")

        elif isinstance(node, StringLiteral):
            lines.append(f"{self._indent_str()}String: \"{node.value}\"")

        elif isinstance(node, BoolLiteral):
            lines.append(f"{self._indent_str()}Bool: {node.value}")

        elif isinstance(node, Identifier):
            lines.append(f"{self._indent_str()}Identifier: {node.name}")

        elif isinstance(node, BinaryOp):
            lines.append(f"{self._indent_str()}BinaryOp: {node.op}")
            self.indent += 1
            self._print_node(node.left, lines)
            self._print_node(node.right, lines)
            self.indent -= 1

        elif isinstance(node, UnaryOp):
            lines.append(f"{self._indent_str()}UnaryOp: {node.op}")
            self.indent += 1
            self._print_node(node.operand, lines)
            self.indent -= 1

        elif isinstance(node, AssignStmt):
            lines.append(f"{self._indent_str()}Assignment: {node.name} =")
            self.indent += 1
            self._print_node(node.value, lines)
            self.indent -= 1

        elif isinstance(node, DeclStmt):
            init_info = " (with init)" if node.init_value else ""
            lines.append(f"{self._indent_str()}Declaration: {node.var_type} {node.name}{init_info}")
            if node.init_value:
                self.indent += 1
                self._print_node(node.init_value, lines)
                self.indent -= 1

        elif isinstance(node, IfStmt):
            lines.append(f"{self._indent_str()}IfStmt")
            self.indent += 1
            lines.append(f"{self._indent_str()}Condition:")
            self.indent += 1
            self._print_node(node.condition, lines)
            self.indent -= 1
            lines.append(f"{self._indent_str()}Then:")
            self.indent += 1
            for stmt in node.then_branch:
                self._print_node(stmt, lines)
            self.indent -= 1
            if node.else_branch:
                lines.append(f"{self._indent_str()}Else:")
                self.indent += 1
                for stmt in node.else_branch:
                    self._print_node(stmt, lines)
                self.indent -= 1
            self.indent -= 1

        elif isinstance(node, WhileStmt):
            lines.append(f"{self._indent_str()}WhileStmt")
            self.indent += 1
            lines.append(f"{self._indent_str()}Condition:")
            self.indent += 1
            self._print_node(node.condition, lines)
            self.indent -= 1
            lines.append(f"{self._indent_str()}Body:")
            self.indent += 1
            for stmt in node.body:
                self._print_node(stmt, lines)
            self.indent -= 1
            self.indent -= 1

        elif isinstance(node, BlockStmt):
            lines.append(f"{self._indent_str()}Block")
            self.indent += 1
            for stmt in node.statements:
                self._print_node(stmt, lines)
            self.indent -= 1


# ==================== 主程序 ====================
# 把所有部分组合起来，提供命令行接口

def analyze_file(filename: str, show_ast: bool = True):
    """
    分析文件的主函数

    步骤：
    1. 读取源文件
    2. 词法分析（切分Token）
    3. 语法分析（检查语法，构建AST）
    4. 打印结果
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误: 找不到文件 '{filename}'")
        return False
    except Exception as e:
        print(f"错误: 读取文件失败 - {e}")
        return False

    return analyze_source(source, show_ast, filename)


def analyze_source(source: str, show_ast: bool = True, filename: str = "<input>"):
    """
    分析源代码的主函数

    这个函数展示了整个编译器前端的流程：
    源代码 -> 词法分析 -> Token序列 -> 语法分析 -> AST
    """
    print(f"\n{'='*60}")
    print(f"分析文件: {filename}")
    print(f"{'='*60}")
    print("源代码:")
    print("-" * 40)
    # 打印源代码，带行号
    for i, line in enumerate(source.split('\n'), 1):
        print(f"{i:3}: {line}")
    print("-" * 40)

    try:
        # 第一步：词法分析
        print("\n开始词法分析...")
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        print("\n词法分析结果 (Token序列):")
        for token in tokens:
            if token.type != TokenType.EOF:
                print(f"  {token}")

        # 第二步：语法分析
        print("\n开始语法分析...")
        parser = Parser(tokens)
        try:
            ast = parser.parse()
        except SyntaxError:
            # 解析过程中发生了错误，parser.errors中已经收集了错误信息
            pass

        # 检查是否有错误
        if parser.errors:
            print("\n" + "="*40)
            print(f"✗ 发现 {len(parser.errors)} 个语法错误")
            print("="*40)
            for i, err in enumerate(parser.errors, 1):
                print(f"\n错误 {i}:")
                print(f"  {err}")
            print("\n" + "="*40)
            return False

        # 成功
        print("\n" + "="*40)
        print("✓ 该程序符合语法要求")
        print("="*40)

        # 第三步：打印AST
        if show_ast:
            print("\n语法树 (AST):")
            print("-" * 40)
            printer = ASTPrinter()
            print(printer.print(ast))

        return True

    except SyntaxError as e:
        # 捕获词法分析阶段的错误
        print("\n" + "="*40)
        print(f"✗ {e}")
        print("="*40)
        return False


def main():
    """
    程序入口

    支持两种模式：
    1. 交互模式：直接运行，输入代码测试
    2. 文件模式：python mini_parser.py test.mini
    """
    if len(sys.argv) < 2:
        # 交互模式
        print("="*60)
        print("Mini语言语法分析器 - 交互模式")
        print("="*60)
        print("输入 Mini 语言代码，按回车分析")
        print("输入 'quit' 或 'exit' 退出")
        print("-" * 40)

        while True:
            try:
                source = input("\n>>> ")
                if source.strip().lower() in ('quit', 'exit'):
                    break
                if source.strip():
                    analyze_source(source, show_ast=True)
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n")
                break
    else:
        # 文件模式
        filename = sys.argv[1]
        show_ast = '--no-ast' not in sys.argv
        success = analyze_file(filename, show_ast)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()



