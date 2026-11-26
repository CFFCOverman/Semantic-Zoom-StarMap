# tools/ 生成脚本
扫描一个技能或项目目录，产出它的星图清单 zoom.json，并做断链、复写和结构检查。推导规则见 `rules.md`。
- [zoomgen.py](zoomgen.py)：扫描源目录 → zoom.json；按登记表重新生成全部清单和 index.json；命令行用法写在它的文件头
