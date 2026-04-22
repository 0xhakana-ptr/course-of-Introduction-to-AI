import fs from 'node:fs'
import path from 'node:path'

const projectRoot = path.resolve(import.meta.dirname, '..')

function copyIfExists(src, dest) {
    if (!fs.existsSync(src)) {
        throw new Error(`Source file not found: ${src}`)
    }
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.copyFileSync(src, dest)
}

try {
    const pkgRoot = path.join(projectRoot, 'node_modules', 'live2dcubismcore')

    copyIfExists(
        path.join(pkgRoot, 'live2dcubismcore.min.js'),
        path.join(projectRoot, 'public', 'live2d', 'live2dcubismcore.min.js'),
    )

    copyIfExists(
        path.join(pkgRoot, 'live2d.min.js'),
        path.join(projectRoot, 'public', 'live2d', 'live2d.min.js'),
    )

    console.log('[sync-live2d-runtime] Synced Live2D runtimes into public/live2d/.')
} catch (err) {
    console.error('[sync-live2d-runtime] Failed:', err)
    process.exitCode = 1
}
