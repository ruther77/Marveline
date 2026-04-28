import type { Plugin } from 'vite'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

interface BrandDescriptor {
  code: string
  name: string
  shortName: string
  description: string
  colors: {
    primary: string
    primaryRgb: string
    palette: Record<string, string>
  }
}

function hexToRgb(hex: string): string {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim())
  if (!m) return '0 0 0'
  return parseInt(m[1], 16) + ' ' + parseInt(m[2], 16) + ' ' + parseInt(m[3], 16)
}

export function loadBrand(brandCode: string, srcDir: string): BrandDescriptor {
  const path = resolve(srcDir, 'brand', brandCode + '.ts')
  let content: string
  try {
    content = readFileSync(path, 'utf-8')
  } catch {
    return {
      code: 'marveline',
      name: 'Marveline',
      shortName: 'Marveline',
      description: 'Location evenementielle',
      colors: {
        primary: '#b96cc4',
        primaryRgb: '185 108 196',
        palette: {
          50: '#fdf5fa', 100: '#f9e8f4', 200: '#f0d0e8', 300: '#dfb7e3',
          400: '#ce8ed4', 500: '#b96cc4', 600: '#9b52a8', 700: '#7e408a',
          800: '#63326d', 900: '#4a2452', 950: '#2d1533',
        },
      },
    }
  }

  const pick = (k: string) => {
    const m = new RegExp(k + ':\\s*[\'"`]([^\'"`]+)[\'"`]').exec(content)
    return m ? m[1] : ''
  }
  const name = pick('name')
  const shortName = pick('shortName') || name
  const description = pick('description')
  const primary = pick('primary')
  const primaryRgb = pick('primaryRgb') || hexToRgb(primary)

  const palette: Record<string, string> = {}
  const paletteBlock = /palette:\s*\{([\s\S]*?)\}/.exec(content)
  if (paletteBlock) {
    const entries = paletteBlock[1].matchAll(/(\d+):\s*['"`]([^'"`]+)['"`]/g)
    for (const [, k, v] of entries) palette[k] = v
  }

  return { code: brandCode, name, shortName, description, colors: { primary, primaryRgb, palette } }
}

/**
 * Resolve le VITE_BRAND courant et charge le brand descriptor.
 * Exporte pour permettre a vite.config.ts de generer le manifest PWA.
 */
export function resolveBrand(): BrandDescriptor {
  const __dirname = dirname(fileURLToPath(import.meta.url))
  const srcDir = resolve(__dirname, '..', 'src')
  const code = process.env.VITE_BRAND ?? 'marveline'
  return loadBrand(code, srcDir)
}

function renderCssVars(brand: BrandDescriptor): string {
  const lines = ['--brand-primary-rgb: ' + brand.colors.primaryRgb + ';']
  for (const [shade, hex] of Object.entries(brand.colors.palette)) {
    lines.push('--brand-primary-' + shade + '-rgb: ' + hexToRgb(hex) + ';')
  }
  return lines.join('\n        ')
}

export function brandHtmlPlugin(options: { srcDir?: string } = {}): Plugin {
  const __dirname = dirname(fileURLToPath(import.meta.url))
  const srcDir = options.srcDir ?? resolve(__dirname, '..', 'src')

  return {
    name: 'brand-html',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        const brandCode = process.env.VITE_BRAND ?? 'marveline'
        const brand = loadBrand(brandCode, srcDir)

        html = html.replace(/<title>[^<]*<\/title>/, '<title>' + brand.name + '</title>')

        html = html.replace(
          /<meta\s+name=["']theme-color["']\s+content=["'][^"']*["']\s*\/?>/,
          '<meta name="theme-color" content="' + brand.colors.primary + '" />',
        )

        const cssVars = renderCssVars(brand)
        const styleBlock = '<style>\n      :root {\n        ' + cssVars + '\n      }\n    </style>'
        html = html.replace(
          /<style>\s*:root\s*\{[\s\S]*?--brand-primary-[\s\S]*?\}\s*<\/style>/,
          styleBlock,
        )

        // Inject data-brand sur <html> + meta pour detection runtime (SW safety net)
        html = html.replace(
          /<html\s+lang=["']fr["']([^>]*)>/,
          '<html lang="fr" data-brand="' + brand.code + '"$1>',
        )
        if (!/<meta\s+name=["']brand-code["']/.test(html)) {
          html = html.replace(
            '<meta charset="UTF-8" />',
            '<meta charset="UTF-8" />\n    <meta name="brand-code" content="' + brand.code + '" />',
          )
        }

        return html
      },
    },
  }
}
