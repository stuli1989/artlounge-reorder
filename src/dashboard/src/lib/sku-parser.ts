import { read, utils } from 'xlsx'

const SKU_COLUMN_PATTERNS = [
  /^sku$/i,
  /^sku.?name$/i,
  /^stock.?item/i,
  /^item.?name$/i,
  /^product.?name$/i,
  /^name$/i,
  /^description$/i,
  /^part.?no/i,
  /^item$/i,
]

/**
 * Parse pasted text into SKU names.
 *
 * Handles:
 * - One SKU per line (newline-separated)
 * - Tab-separated (pasted from Excel column)
 *
 * Strips empty lines, trims whitespace, deduplicates.
 */
export function parsePastedText(text: string): string[] {
  const lines = text.split(/\r?\n/)
  const names: string[] = []

  for (const line of lines) {
    // If line has tabs (Excel paste), split by tab and take each cell
    if (line.includes('\t')) {
      for (const cell of line.split('\t')) {
        const trimmed = cell.trim()
        if (trimmed) names.push(trimmed)
      }
    } else {
      const trimmed = line.trim()
      if (trimmed) names.push(trimmed)
    }
  }

  return dedupe(names)
}

/**
 * Parse an Excel (.xlsx/.xls) or CSV file into SKU names.
 *
 * Strategy:
 * 1. Read the first sheet
 * 2. Look for a header row containing a SKU-like column name
 * 3. If found, extract that column's values
 * 4. If not found, take the first column's values (skip header if it looks like one)
 */
export async function parseFile(file: File): Promise<string[]> {
  const buffer = await file.arrayBuffer()
  const workbook = read(buffer, { type: 'array' })

  const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
  if (!firstSheet) return []

  const rows: string[][] = utils.sheet_to_json(firstSheet, { header: 1 })
  if (rows.length === 0) return []

  // Find the SKU column by header name
  const headerRow = rows[0]

  let skuColIndex = -1
  if (headerRow) {
    for (let col = 0; col < headerRow.length; col++) {
      const header = String(headerRow[col] ?? '').trim()
      if (SKU_COLUMN_PATTERNS.some(p => p.test(header))) {
        skuColIndex = col
        break
      }
    }
  }

  const names: string[] = []
  const colIdx = skuColIndex >= 0 ? skuColIndex : 0

  // Skip first row if we identified it as a header
  const firstCell = String(rows[0]?.[colIdx] ?? '').trim().toLowerCase()
  const looksLikeHeader = skuColIndex >= 0 || SKU_COLUMN_PATTERNS.some(p => p.test(firstCell))
  const startRow = looksLikeHeader ? 1 : 0

  for (let i = startRow; i < rows.length; i++) {
    const val = String(rows[i]?.[colIdx] ?? '').trim()
    if (val && val.toLowerCase() !== 'null' && val !== '0') {
      names.push(val)
    }
  }

  return dedupe(names)
}

function dedupe(names: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const name of names) {
    const key = name.toLowerCase()
    if (!seen.has(key)) {
      seen.add(key)
      result.push(name)
    }
  }
  return result
}
