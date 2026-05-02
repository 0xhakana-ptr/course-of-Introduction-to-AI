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

    const coreNoSync = String(process.env.LIVE2D_CUBISM_CORE_NO_SYNC ?? '').trim() === '1'
    const coreOverrideRaw = String(process.env.LIVE2D_CUBISM_CORE_SRC ?? '').trim()
    const coreOverride = coreOverrideRaw
        ? (path.isAbsolute(coreOverrideRaw) ? coreOverrideRaw : path.join(projectRoot, coreOverrideRaw))
        : null

    const coreSrc = coreOverride ?? path.join(pkgRoot, 'live2dcubismcore.min.js')

    if (!coreNoSync) {
        copyIfExists(
            coreSrc,
            path.join(projectRoot, 'public', 'live2d', 'live2dcubismcore.min.js'),
        )
    }

    copyIfExists(
        path.join(pkgRoot, 'live2d.min.js'),
        path.join(projectRoot, 'public', 'live2d', 'live2d.min.js'),
    )

    console.log('[sync-live2d-runtime] Synced Live2D runtimes into public/live2d/.')
    if (coreNoSync) {
        console.log('[sync-live2d-runtime] Skipped Cubism Core sync (LIVE2D_CUBISM_CORE_NO_SYNC=1).')
    } else if (coreOverride) {
        console.log('[sync-live2d-runtime] Using overridden Cubism Core:', coreOverride)
    }
} catch (err) {
    console.error('[sync-live2d-runtime] Failed:', err)
    process.exitCode = 1
}
