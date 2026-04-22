# Live2D 资源放置说明

把你的 Live2D Cubism 模型文件放在这里（`public/live2d/`），构建后会原样复制到 `dist/live2d/`。

当前默认加载：

- `public/live2d/mianfeimox/llny.model3.json`

## 运行库（必须）

`pixi-live2d-display` 不会直接通过 npm 自带 Live2D 的核心运行库文件。

本项目已接入一个“本地同步”方案：安装依赖后，在每次运行 `pnpm dev` / `pnpm build` 时，会自动把运行库同步到 `public/live2d/`：

- `public/live2d/live2dcubismcore.min.js`
- `public/live2d/live2d.min.js`

因此在你网络环境不好、无法从官网拿到 `_em_module.wasm` 的情况下，也可以先把项目跑起来。

- 如果你的模型是 **Cubism 4/3**（文件名通常是 `*.model3.json`）
	- 通常需要：
		- `public/live2d/live2dcubismcore.min.js`
		- 部分官方 Core 版本还需要 `.wasm`（例如 `_em_module.wasm` 或 `live2dcubismcore.wasm`）
		- 但如果你使用的是本项目通过依赖同步出来的 core（默认），它是不依赖 `.wasm` 的
- 如果你的模型是 **Cubism 2**（文件名通常是 `*.model.json`）
	- 需要：`public/live2d/live2d.min.js`

本项目会根据模型文件名自动选择 `cubism4` / `cubism2` 入口，并在缺少运行库时在窗口底部提示缺哪个文件。

你只需要确保该路径存在（以及它引用的纹理/动作/物理等文件也在同一目录结构中），即可在：

- Web（Vite dev/preview）
- Electron（`file://.../dist/`）

两种环境正常加载。

如果你要改默认路径：

- 修改 `src/App.vue` 里的 `DEFAULT_MODEL_JSON_PATH`
