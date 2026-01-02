# Mini语言语法分析器

这是一个完整的Mini语言语法分析器实现，包含词法分析、语法分析和AST构建功能。

## 功能特性

- **词法分析**：将源代码切分成Token序列
- **语法分析**：使用递归下降法检查语法正确性
- **AST构建**：生成抽象语法树
- **错误处理**：提供详细的错误位置和信息
- **错误恢复**：使用恐慌模式继续分析

## 支持的语言特性

### 数据类型
- `int` - 整数
- `float` - 浮点数
- `bool` - 布尔值
- `string` - 字符串

### 语句
- 变量声明：`int x = 5;`
- 赋值语句：`x = 10;`
- if语句：`if x > 0 then ... else ... end`
- while循环：`while i < 10 do ... end`
- 代码块：`begin ... end`

### 表达式
- 算术运算：`+`, `-`, `*`, `/`
- 比较运算：`==`, `!=`, `<`, `>`, `<=`, `>=`
- 逻辑运算：`and`, `or`, `not`（也支持`&&`, `||`, `!`）
- 括号表达式：`(expr)`
- 一元运算：`-x`, `+x`, `not flag`

### 注释
- 单行注释：`// 这是注释`

## 使用方法

### 1. 分析文件
```bash
python3 mini_parser.py program.mini
```

### 2. 分析文件（不显示AST）
```bash
python3 mini_parser.py program.mini --no-ast
```

### 3. 交互模式
```bash
python3 mini_parser.py
>>> int x = 5;
```

### 4. 运行所有测试
```bash
python3 run_all_tests.py
```

## 示例程序

### 示例1：计算1到n的和
```mini
int n = 10;
int sum = 0;
int i = 1;

while i <= n do
    sum = sum + i;
    i = i + 1;
end
```

### 示例2：判断正负数
```mini
int x = -5;

if x > 0 then
    x = 1;
else
    if x < 0 then
        x = -1;
    else
        x = 0;
    end
end
```

### 示例3：逻辑运算
```mini
bool a = true;
bool b = false;
bool result = (a and not b) or (not a and b);
```

## 文件结构

```
mini-language-parser/
├── mini_parser.py           # 主程序（词法分析+语法分析+AST）
├── run_all_tests.py         # 自动化测试脚本
├── test_cases/              # 测试用例目录
│   ├── TEST_REPORT.md       # 测试报告
│   ├── test_pass_01_basic.mini   # 正确语法测试
│   ├── test_pass_02_arithmetic.mini
│   ├── ...                  # 更多测试文件
│   └── test_fail_*.mini     # 错误测试（预期失败）
└── README.md                # 本文件
```

## 测试覆盖

已创建55个测试用例，其中：
- ✓ 36个通过用例（test_pass_*）
- ✓ 19个失败用例（test_fail_*，预期报错）

所有测试100%通过，详见 `test_cases/TEST_REPORT.md`。

## 代码结构

### 1. 词法分析器（Lexer）
- `class TokenType` - Token类型枚举
- `class Token` - Token数据结构
- `class Lexer` - 词法分析器
  - `tokenize()` - 主要方法，返回Token列表

### 2. AST节点定义
- `Program` - 程序根节点
- `DeclStmt` - 变量声明
- `AssignStmt` - 赋值语句
- `IfStmt` - if语句
- `WhileStmt` - while循环
- `BlockStmt` - 代码块
- `BinaryOp` - 二元运算
- `UnaryOp` - 一元运算
- `Identifier`, `NumberLiteral`, `StringLiteral`, `BoolLiteral` - 字面量

### 3. 语法分析器（Parser）
- `class Parser` - 递归下降语法分析器
  - `parse()` - 入口方法
  - `parse_stmt()` - 解析语句
  - `parse_expr()` - 解析表达式
  - `parse_logic_or/and/not()` - 逻辑运算（优先级递减）
  - `parse_comparison()` - 比较运算
  - `parse_arith_expr()` - 算术表达式（加减）
  - `parse_term()` - 项（乘除）
  - `parse_factor()` - 因子（最基本元素）
  - `synchronize()` - 错误恢复

### 4. AST打印器（ASTPrinter）
- `class ASTPrinter` - 树状打印AST
  - `print()` - 打印整棵树

## 文法定义（非左递归版本）

```
Program     -> StmtList
StmtList    -> Stmt StmtList | ε
Stmt        -> DeclStmt | AssignStmt | IfStmt | WhileStmt | BlockStmt | Expr ';'
DeclStmt    -> Type ID ('=' Expr)? ';'
AssignStmt  -> ID '=' Expr ';'
IfStmt      -> 'if' Expr 'then' StmtList ('else' StmtList)? 'end'
WhileStmt   -> 'while' Expr 'do' StmtList 'end'
BlockStmt   -> 'begin' StmtList 'end'
Expr        -> LogicOr
LogicOr     -> LogicAnd (('or'|'||') LogicAnd)*
LogicAnd    -> LogicNot (('and'|'&&') LogicNot)*
LogicNot    -> ('not'|'!') LogicNot | Comparison
Comparison  -> ArithExpr (CompOp ArithExpr)?
ArithExpr   -> Term (('+' | '-') Term)*
Term        -> Factor (('*' | '/') Factor)*
Factor      -> '(' Expr ')' | Number | String | Bool | ID | ('+'|'-') Factor
```

## 运算符优先级（从低到高）

1. 逻辑或：`or`, `||`
2. 逻辑与：`and`, `&&`
3. 逻辑非：`not`, `!`
4. 比较：`==`, `!=`, `<`, `>`, `<=`, `>=`
5. 加减：`+`, `-`
6. 乘除：`*`, `/`
7. 一元：`-`, `+`, `not`, `!`
8. 括号：`()`

## 已知问题与限制

无已知问题。所有测试通过，包括：
- ✓ 复杂嵌套结构
- ✓ 各种错误情况
- ✓ 边界情况
- ✓ 空程序和空语句块

## 开发说明

### 已修复的Bug
1. **死循环问题**（已修复）
   - 问题：缺少`then`关键字时会死循环
   - 原因：`parse_stmt_list`中位置未移动检测缺失
   - 修复：添加位置检测机制和END/ELSE同步点

### 代码质量
- 完整的注释和文档
- 清晰的错误信息
- 健壮的错误处理
- 良好的代码结构

## 作者

本项目为编译原理课程的语法分析实习作业。

## 许可

Educational use only.
