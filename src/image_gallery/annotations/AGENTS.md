# `annotations/` 模块指南

## 职责

- 提供外部标注格式与 ImageGallery Dataset 之间的互操作能力。
- 当前只负责 LabelImg/Pascal VOC 加载与导出，不扩展到未要求的标注平台。

## 当前能力与公共入口

从 `image_gallery.annotations` 使用 `LabelImgLoader` 和 `LabelImgExporter`。

## 核心契约与边界

- 标注适配器通过 Dataset Loader/Exporter 协议接入。
- LabelImg 目录约定、bbox 坐标语义和失败结果必须与 Dataset I/O 契约一致。
- 不在此模块实现通用图片存储或数据集核心读写。

## 开发与验证

- 单元测试：`tests/unit/annotations/`
- 当前行为：`openspec/specs/annotations/spec.md`、`openspec/specs/dataset-management/spec.md`
