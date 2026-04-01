import { useState, useCallback, useRef } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { ClipboardPaste, Upload, FileSpreadsheet, X, Loader2, Search, Hash } from 'lucide-react'
import { parsePastedText, parseFile } from '@/lib/sku-parser'
import { Input } from '@/components/ui/input'
import { fetchPrefixSearch } from '@/lib/api'
import type { PrefixSearchResponse } from '@/lib/types'

interface SkuInputDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (skuNames: string[]) => void
  isLoading?: boolean
}

export default function SkuInputDialog({ open, onOpenChange, onSubmit, isLoading }: SkuInputDialogProps) {
  const [pasteText, setPasteText] = useState('')
  const [parsedNames, setParsedNames] = useState<string[]>([])
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [prefixQuery, setPrefixQuery] = useState('')
  const [prefixLoading, setPrefixLoading] = useState(false)
  const [prefixResult, setPrefixResult] = useState<PrefixSearchResponse | null>(null)
  const [prefixError, setPrefixError] = useState<string | null>(null)

  const handlePasteChange = (text: string) => {
    setPasteText(text)
    setParsedNames(parsePastedText(text))
    setFileName(null)
    setFileError(null)
  }

  const handleFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['xlsx', 'xls', 'csv'].includes(ext)) {
      setFileError('Unsupported file type. Use .xlsx, .xls, or .csv')
      return
    }
    try {
      setFileError(null)
      setFileName(file.name)
      const names = await parseFile(file)
      setParsedNames(names)
      setPasteText('')
    } catch {
      setFileError('Failed to parse file. Make sure it is a valid Excel or CSV file.')
      setFileName(null)
      setParsedNames([])
    }
  }, [])

  const handlePrefixSearch = async () => {
    const q = prefixQuery.trim()
    if (q.length < 2) {
      setPrefixError('Enter at least 2 characters')
      return
    }
    setPrefixLoading(true)
    setPrefixError(null)
    try {
      const result = await fetchPrefixSearch(q)
      setPrefixResult(result)
      if (result.total === 0) {
        setPrefixError(`No SKUs found with part number starting "${q}"`)
      } else {
        setParsedNames(result.skus.map(s => s.item_code))
      }
    } catch {
      setPrefixError('Search failed — try again')
    } finally {
      setPrefixLoading(false)
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleSubmit = () => {
    if (parsedNames.length > 0) {
      onSubmit(parsedNames)
    }
  }

  const handleClose = () => {
    setPasteText('')
    setParsedNames([])
    setFileName(null)
    setFileError(null)
    setPrefixQuery('')
    setPrefixResult(null)
    setPrefixError(null)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import SKU List</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="paste">
          <TabsList className="w-full">
            <TabsTrigger value="paste" className="flex-1 gap-1.5">
              <ClipboardPaste className="h-3.5 w-3.5" /> Paste
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex-1 gap-1.5">
              <Upload className="h-3.5 w-3.5" /> Upload
            </TabsTrigger>
            <TabsTrigger value="prefix" className="flex-1 gap-1.5">
              <Hash className="h-3.5 w-3.5" /> Code Prefix
            </TabsTrigger>
          </TabsList>

          <TabsContent value="paste" className="mt-3">
            <textarea
              className="w-full h-48 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none font-mono"
              placeholder={"Paste SKU names, one per line:\n\nWN COTMAN WATERCOLOUR 8ML CADMIUM RED\nSennelier L Aquarelle 10Ml Sennelier Red\nHolbein AWC Scarlet Lake B 5ml\n\nOr paste a column from Excel (tab-separated)"}
              value={pasteText}
              onChange={e => handlePasteChange(e.target.value)}
            />
          </TabsContent>

          <TabsContent value="upload" className="mt-3">
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
              }`}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              {fileName ? (
                <div className="space-y-2">
                  <FileSpreadsheet className="h-8 w-8 mx-auto text-green-600" />
                  <p className="text-sm font-medium">{fileName}</p>
                  <Button variant="ghost" size="sm" onClick={() => { setFileName(null); setParsedNames([]); setFileError(null) }}>
                    <X className="h-3 w-3 mr-1" /> Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">
                      Drag & drop an Excel or CSV file here
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Supports .xlsx, .xls, .csv
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                    Browse Files
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                </div>
              )}
            </div>
            {fileError && (
              <p className="text-sm text-red-600 mt-2">{fileError}</p>
            )}
          </TabsContent>

          <TabsContent value="prefix" className="mt-3">
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter part number prefix, e.g. 0102"
                  value={prefixQuery}
                  onChange={e => {
                    setPrefixQuery(e.target.value)
                    setPrefixResult(null)
                    setPrefixError(null)
                  }}
                  onKeyDown={e => { if (e.key === 'Enter') handlePrefixSearch() }}
                  className="flex-1 font-mono"
                />
                <Button onClick={handlePrefixSearch} disabled={prefixLoading || prefixQuery.trim().length < 2}>
                  {prefixLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>

              {prefixError && (
                <p className="text-sm text-red-600">{prefixError}</p>
              )}

              {prefixResult && prefixResult.total > 0 && (
                <div className="space-y-2">
                  <div className="text-sm text-muted-foreground bg-muted/50 rounded px-3 py-2 border">
                    <strong className="text-foreground">{prefixResult.total}</strong> SKU{prefixResult.total !== 1 ? 's' : ''} across{' '}
                    <strong className="text-foreground">{prefixResult.brands.length}</strong> brand{prefixResult.brands.length !== 1 ? 's' : ''}:
                    <div className="text-xs mt-1">{prefixResult.brands.join(', ')}</div>
                  </div>
                  <div className="max-h-48 overflow-y-auto border rounded text-xs">
                    {prefixResult.skus.slice(0, 50).map(s => (
                      <div key={s.item_code} className="px-3 py-1.5 border-b last:border-b-0 flex items-center justify-between">
                        <span className="font-mono text-muted-foreground mr-2">{s.display_name}</span>
                        <span className="truncate flex-1">{s.item_code}</span>
                      </div>
                    ))}
                    {prefixResult.total > 50 && (
                      <div className="px-3 py-1.5 text-muted-foreground text-center">
                        +{prefixResult.total - 50} more
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Preview count */}
        {parsedNames.length > 0 && (
          <div className="text-sm text-muted-foreground bg-muted/50 rounded px-3 py-2 border">
            <strong className="text-foreground">{parsedNames.length}</strong> unique SKU name{parsedNames.length !== 1 ? 's' : ''} detected
            {parsedNames.length > 500 && (
              <p className="text-red-600 text-xs mt-1">Maximum 500 SKUs. Only the first 500 will be submitted.</p>
            )}
            {parsedNames.length <= 5 && (
              <ul className="mt-1 text-xs space-y-0.5">
                {parsedNames.map((n, i) => <li key={i} className="truncate">• {n}</li>)}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={parsedNames.length === 0 || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
            Match & Build PO
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
