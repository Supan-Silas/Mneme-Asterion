# Mneme-Asterion E 完整系统：来源与改动

基础方法为 Xuhao Lin 的 ActiveMemoryIndex：https://github.com/linxuhao/ActiveMemoryIndex 。原MIT版权通知完整保留于根目录LICENSE。

app/ 是本轮实际评测B0的逐字源码快照，导出hash见EXPORT_HASHES.json；本次未修改其算法文件。其历史复现来源及改动说明存于provenance/B0_ATTRIBUTION.md和provenance/B0_SOURCE_ORIGIN.json，历史文档所述部分上游目录不属于本精简运行包。未知的上游commit不补造。

E设计参考本地ReFind README的原始聊天块、BM25、邻接上下文和按证据继续搜索思路。E是AMI上的有界原文补充，不是完整ReFind复现；未复制ReFind实现。当前源码源于本项目冻结实验，不将上游方法包装成独立原创算法。

e_core/ 是冻结E代码，仅改为包内相对导入及规范换行；原字节保存在framework_reference/frozen_e，测试同时核对原hash和规范化文本。未启用文件中的D过滤路径。

新增mneme_e/提供原文持久化、成功写入可见性、完整API、配置入口与E模型调用。service中的FULL持久化和用户串行锁是本次工程集成，不属于原上游算法。framework_reference的打包/适配代码只用于解释评测口径，运行时不依赖旧benchmark。

本目录是完整记忆服务，不包含Reader/Judge或题库。旧成绩是冻结B0记忆上的E检索消融；新的完整服务已另做合成HTTP/真实模型链路验证，不借用旧成绩声称全量重跑。
