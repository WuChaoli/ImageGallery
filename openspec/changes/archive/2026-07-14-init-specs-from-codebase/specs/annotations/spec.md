## ADDED Requirements

### Requirement: LabelImgExporter 标注导出
系统 SHALL 提供 `LabelImgExporter`，把 Dataset 导出为 LabelImg 兼容的 Pascal VOC XML 标注目录。

#### Scenario: 导出标注目录
- **WHEN** 调用 `LabelImgExporter(output_dir).export(dataset)`
- **THEN** 在 output_dir 下创建 images/ 和 annotations/ 子目录，写出图片文件和可选 XML 标注文件

#### Scenario: 导出包含 Dataset 副本
- **WHEN** 导出完成
- **THEN** output_dir 中包含 raw.parquet Dataset 文件副本

#### Scenario: 导出覆盖保护
- **WHEN** output_dir 已存在且 overwrite=False
- **THEN** 抛出 FileExistsError

#### Scenario: 图片扩展名推断
- **WHEN** Dataset 行中 file_extension 列为空
- **THEN** 从 source_file_name 或 image_uri 推断扩展名，或通过 Pillow 读取图片格式

#### Scenario: image_id 唯一性校验
- **WHEN** Dataset 中存在重复的 image_id
- **THEN** 抛出 ValueError

### Requirement: LabelImgLoader 标注加载
系统 SHALL 提供 `LabelImgLoader`，从 LabelImg Pascal VOC 标注目录加载带 annotations 列的 Dataset。

#### Scenario: 加载标注目录
- **WHEN** 调用 `LabelImgLoader(input_dir).load()`
- **THEN** 读取 raw.parquet 和 annotations/*.xml，写出 labeled.parquet 并返回 Dataset

#### Scenario: 标注尺寸不匹配
- **WHEN** XML 标注中的 width/height 与 Dataset 中的不一致且 strict=True
- **THEN** 抛出 ValueError

#### Scenario: 非严格模式跳过错误
- **WHEN** strict=False 且某些 XML 标注无法匹配
- **THEN** 跳过错误标注，在 labelimg_load_report.json 中记录失败列表

#### Scenario: annotations 列
- **WHEN** 加载完成
- **THEN** Dataset 的 annotations 列包含每张图片的标注列表（dict 格式）

### Requirement: Pascal VOC XML 读写
系统 SHALL 提供 `read_pascal_voc_xml()` 和 `write_pascal_voc_xml()` 函数，支持 LabelImg 兼容的 Pascal VOC XML 格式。

#### Scenario: 读取 XML
- **WHEN** 调用 `read_pascal_voc_xml(xml_path)` 读取标准 Pascal VOC XML
- **THEN** 返回 PascalVocAnnotation，包含 filename、width、height、depth 和 annotations 列表

#### Scenario: 写出 XML
- **WHEN** 调用 `write_pascal_voc_xml()` 传入 annotations 列表
- **THEN** 写出 LabelImg 可读取的 Pascal VOC XML 文件

#### Scenario: 相对坐标转 VOC 像素坐标
- **WHEN** 调用 `relative_bbox_to_voc_bbox(annotation, width=1920, height=1080)`
- **THEN** 把相对坐标 [0,1] 乘以宽高转换为整数像素坐标

#### Scenario: VOC 像素坐标转相对坐标
- **WHEN** 调用 `voc_bbox_to_annotation()` 传入像素坐标和宽高
- **THEN** 返回相对坐标 [0,1] 格式的标注 dict，format 字段为 "relative_xyxy"
