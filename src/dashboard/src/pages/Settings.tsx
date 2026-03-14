import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchSettings, updateSetting, fetchSuppliers } from '@/lib/api'
import type { Supplier } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Settings as SettingsIcon, Shield, Clock, BarChart3, Snowflake, Tags, ArrowRight, Check, Loader2, Info } from 'lucide-react'
import HelpTip from '@/components/HelpTip'

const SIDEBAR_SECTIONS = [
  { id: 'safety-buffers', label: 'Safety Buffers', icon: Shield },
  { id: 'lead-times', label: 'Lead Times', icon: Clock },
  { id: 'analysis-defaults', label: 'Analysis Defaults', icon: BarChart3 },
  { id: 'dead-stock', label: 'Dead Stock Thresholds', icon: Snowflake },
  { id: 'classification', label: 'Classification', icon: Tags },
]

export default function Settings() {
  const queryClient = useQueryClient()
  const [activeSection, setActiveSection] = useState('safety-buffers')
  const contentRef = useRef<HTMLDivElement>(null)

  // --- Data fetching ---
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  })

  const { data: suppliers, isLoading: suppliersLoading } = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
  })

  // --- Local state for editable fields ---
  const [useXyzBuffer, setUseXyzBuffer] = useState(false)
  const [bufferA, setBufferA] = useState('')
  const [bufferB, setBufferB] = useState('')
  const [bufferC, setBufferC] = useState('')
  const [velocityType, setVelocityType] = useState('')
  const [dateRange, setDateRange] = useState('')
  const [deadStockDays, setDeadStockDays] = useState('')
  const [slowMoverMonthly, setSlowMoverMonthly] = useState('')

  // Populate local state from fetched settings
  useEffect(() => {
    if (!settings) return
    setUseXyzBuffer(settings.use_xyz_buffer === 'true')
    setBufferA(settings.buffer_a || '1.5')
    setBufferB(settings.buffer_b || '1.0')
    setBufferC(settings.buffer_c || '0.5')
    setVelocityType(settings.default_velocity_type || 'flat')
    setDateRange(settings.default_date_range || 'full_fy')
    setDeadStockDays(settings.dead_stock_threshold_days || '30')
    if (settings.slow_mover_velocity_threshold) {
      setSlowMoverMonthly(String((parseFloat(settings.slow_mover_velocity_threshold) * 30).toFixed(1)))
    } else {
      setSlowMoverMonthly('3.0')
    }
  }, [settings])

  // --- Mutation ---
  const saveMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => updateSetting(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })

  const [lastSavedKey, setLastSavedKey] = useState<string | null>(null)

  const save = (key: string, value: string) => {
    setLastSavedKey(key)
    saveMutation.mutate({ key, value })
  }

  const isSaving = (key: string) => saveMutation.isPending && lastSavedKey === key
  const justSaved = (key: string) => saveMutation.isSuccess && lastSavedKey === key && !saveMutation.isPending

  // --- Scroll-to-section ---
  const scrollToSection = (id: string) => {
    setActiveSection(id)
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  // Track active section on scroll
  useEffect(() => {
    const container = contentRef.current
    if (!container) return

    const handleScroll = () => {
      const sections = SIDEBAR_SECTIONS.map(s => ({
        id: s.id,
        el: document.getElementById(s.id),
      })).filter(s => s.el)

      for (const section of sections.reverse()) {
        if (section.el) {
          const rect = section.el.getBoundingClientRect()
          if (rect.top <= 200) {
            setActiveSection(section.id)
            break
          }
        }
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  // --- Helper for buffer display ---
  const bufferLabel = (cls: string) => {
    switch (cls) {
      case 'A': return 'A-class (high revenue)'
      case 'B': return 'B-class (medium revenue)'
      case 'C': return 'C-class (low revenue)'
      default: return cls
    }
  }

  const SaveButton = ({ settingKey, value, disabled }: { settingKey: string; value: string; disabled?: boolean }) => (
    <Button
      size="sm"
      variant="outline"
      disabled={disabled || isSaving(settingKey)}
      onClick={() => save(settingKey, value)}
      className="min-w-[70px]"
    >
      {isSaving(settingKey) ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : justSaved(settingKey) ? (
        <><Check className="h-3.5 w-3.5 mr-1" /> Saved</>
      ) : (
        'Save'
      )}
    </Button>
  )

  if (settingsLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="h-96 bg-muted animate-pulse rounded-lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Settings</h2>
      </div>

      {/* Layout: sidebar + content */}
      <div className="flex gap-6">
        {/* Sidebar Navigation */}
        <nav className="w-[200px] shrink-0 space-y-1 sticky top-6 self-start">
          {SIDEBAR_SECTIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => scrollToSection(id)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors text-left ${
                activeSection === id
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Content Area */}
        <div ref={contentRef} className="flex-1 space-y-8 min-w-0">

          {/* ===== Safety Buffers ===== */}
          <section id="safety-buffers">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Safety Buffers
                </CardTitle>
                <CardDescription>
                  Control how much extra stock to recommend beyond lead-time demand.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* XYZ Toggle */}
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-1">
                    <Label className="text-sm font-medium">Use XYZ-adjusted buffers <HelpTip tip="Demand variability scoring. Currently 99.6% of SKUs are Z-class (sporadic), so this adds little discrimination for art supplies." helpAnchor="abc-classification" /></Label>
                    <p className="text-xs text-muted-foreground">
                      When enabled, buffers are adjusted by demand variability (XYZ class).
                      {useXyzBuffer ? ' Currently: ABC+XYZ mode.' : ' Currently: ABC-only mode.'}
                    </p>
                  </div>
                  <Switch
                    checked={useXyzBuffer}
                    onCheckedChange={(checked: boolean) => {
                      setUseXyzBuffer(checked)
                      save('use_xyz_buffer', String(checked))
                    }}
                  />
                </div>

                {/* ABC Buffer Table */}
                <div className="space-y-3">
                  <Label className="text-sm font-medium">ABC Class Buffer Multipliers</Label>
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Class</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead className="w-[120px]">Buffer Multiplier</TableHead>
                          <TableHead className="w-[100px]"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {[
                          { cls: 'A', value: bufferA, setter: setBufferA, key: 'buffer_a' },
                          { cls: 'B', value: bufferB, setter: setBufferB, key: 'buffer_b' },
                          { cls: 'C', value: bufferC, setter: setBufferC, key: 'buffer_c' },
                        ].map(({ cls, value, setter, key }) => (
                          <TableRow key={cls}>
                            <TableCell className="font-medium">{cls}</TableCell>
                            <TableCell className="text-muted-foreground text-sm">{bufferLabel(cls)}</TableCell>
                            <TableCell>
                              <Input
                                type="number"
                                min={0}
                                step={0.1}
                                value={value}
                                onChange={e => setter(e.target.value)}
                                className="h-8 w-[100px]"
                              />
                            </TableCell>
                            <TableCell>
                              <SaveButton
                                settingKey={key}
                                value={value}
                                disabled={!value || isNaN(parseFloat(value)) || parseFloat(value) < 0}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>

                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Buffer changes take effect on the next nightly sync. Existing SKU metrics will be recalculated.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </section>

          {/* ===== Lead Times ===== */}
          <section id="lead-times">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Lead Times
                </CardTitle>
                <CardDescription>
                  Supplier lead times used for reorder calculations. Manage via the Suppliers page.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {suppliersLoading ? (
                  <div className="text-center py-8 text-muted-foreground">Loading suppliers...</div>
                ) : (suppliers || []).length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No suppliers configured yet.
                  </div>
                ) : (
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Supplier</TableHead>
                          <TableHead className="text-right">Sea (days)</TableHead>
                          <TableHead className="text-right">Air (days)</TableHead>
                          <TableHead className="text-right">Default (days)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(suppliers as Supplier[]).map(s => (
                          <TableRow key={s.id}>
                            <TableCell className="font-medium">{s.name}</TableCell>
                            <TableCell className="text-right">{s.lead_time_sea ?? '-'}</TableCell>
                            <TableCell className="text-right">{s.lead_time_air ?? '-'}</TableCell>
                            <TableCell className="text-right">{s.lead_time_default}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                <Link
                  to="/suppliers"
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  Manage suppliers <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </CardContent>
            </Card>
          </section>

          {/* ===== Analysis Defaults ===== */}
          <section id="analysis-defaults">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Analysis Defaults
                </CardTitle>
                <CardDescription>
                  Default velocity calculation method and date range for new sessions.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Velocity Type */}
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label className="text-sm font-medium">Velocity Calculation</Label>
                    <p className="text-xs text-muted-foreground">
                      Flat uses simple average; WMA weights recent months more heavily.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={velocityType} onValueChange={v => {
                      if (!v) return
                      setVelocityType(v)
                      save('default_velocity_type', v)
                    }}>
                      <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Select method" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="flat">Flat (Simple Average)</SelectItem>
                        <SelectItem value="wma">WMA (Weighted Moving Avg)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Separator />

                {/* Default Date Range */}
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label className="text-sm font-medium">Default Date Range</Label>
                    <p className="text-xs text-muted-foreground">
                      The analysis period shown when opening a brand or SKU page.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={dateRange} onValueChange={v => {
                      if (!v) return
                      setDateRange(v)
                      save('default_date_range', v)
                    }}>
                      <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Select range" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="full_fy">Full Financial Year</SelectItem>
                        <SelectItem value="6m">Last 6 Months</SelectItem>
                        <SelectItem value="3m">Last 3 Months</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Users can override these defaults per session on any brand or SKU page.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </section>

          {/* ===== Dead Stock Thresholds ===== */}
          <section id="dead-stock">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Snowflake className="h-4 w-4" />
                  Dead Stock Thresholds
                </CardTitle>
                <CardDescription>
                  Configure when items are flagged as dead stock or slow movers.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Dead Stock Threshold */}
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label className="text-sm font-medium">Dead Stock Threshold</Label>
                    <p className="text-xs text-muted-foreground">
                      Items with no sales for this many days are flagged as dead stock.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      min={1}
                      value={deadStockDays}
                      onChange={e => setDeadStockDays(e.target.value)}
                      className="h-8 w-[80px]"
                    />
                    <span className="text-sm text-muted-foreground">days</span>
                    <SaveButton
                      settingKey="dead_stock_threshold_days"
                      value={deadStockDays}
                      disabled={!deadStockDays || isNaN(parseInt(deadStockDays)) || parseInt(deadStockDays) < 1 || deadStockDays === settings?.dead_stock_threshold_days}
                    />
                  </div>
                </div>

                <Separator />

                {/* Slow Mover Threshold */}
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label className="text-sm font-medium">Slow Mover Velocity Threshold</Label>
                    <p className="text-xs text-muted-foreground">
                      Items selling below this rate are flagged as slow movers.
                      Stored as daily velocity internally ({slowMoverMonthly ? (parseFloat(slowMoverMonthly) / 30).toFixed(4) : '—'}/day).
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={slowMoverMonthly}
                      onChange={e => setSlowMoverMonthly(e.target.value)}
                      className="h-8 w-[80px]"
                    />
                    <span className="text-sm text-muted-foreground">units/mo</span>
                    <SaveButton
                      settingKey="slow_mover_velocity_threshold"
                      value={slowMoverMonthly ? (parseFloat(slowMoverMonthly) / 30).toFixed(6) : ''}
                      disabled={
                        !slowMoverMonthly ||
                        isNaN(parseFloat(slowMoverMonthly)) ||
                        parseFloat(slowMoverMonthly) <= 0 ||
                        slowMoverMonthly === String((parseFloat(settings?.slow_mover_velocity_threshold || '0') * 30).toFixed(1))
                      }
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ===== Classification ===== */}
          <section id="classification">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Tags className="h-4 w-4" />
                  Classification
                </CardTitle>
                <CardDescription>
                  ABC and XYZ classification thresholds. Not configurable in V1.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* ABC Thresholds */}
                <div className="space-y-3">
                  <Label className="text-sm font-medium">ABC Classification (Revenue-based)</Label>
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Class</TableHead>
                          <TableHead>Cumulative Revenue Threshold</TableHead>
                          <TableHead>Description</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow>
                          <TableCell className="font-medium">A</TableCell>
                          <TableCell>Top 80%</TableCell>
                          <TableCell className="text-muted-foreground text-sm">High-value items driving most revenue</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="font-medium">B</TableCell>
                          <TableCell>80% - 95%</TableCell>
                          <TableCell className="text-muted-foreground text-sm">Medium-value items</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="font-medium">C</TableCell>
                          <TableCell>95% - 100%</TableCell>
                          <TableCell className="text-muted-foreground text-sm">Low-value, long-tail items</TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </div>

                <Separator />

                {/* XYZ Thresholds */}
                <div className="space-y-3">
                  <Label className="text-sm font-medium">XYZ Classification (Demand Variability)</Label>
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Class</TableHead>
                          <TableHead>Coefficient of Variation (CV)</TableHead>
                          <TableHead>Description</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow>
                          <TableCell className="font-medium">X</TableCell>
                          <TableCell>CV &lt; 0.5</TableCell>
                          <TableCell className="text-muted-foreground text-sm">Stable, predictable demand</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="font-medium">Y</TableCell>
                          <TableCell>0.5 &le; CV &lt; 1.0</TableCell>
                          <TableCell className="text-muted-foreground text-sm">Variable demand, some seasonality</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="font-medium">Z</TableCell>
                          <TableCell>CV &ge; 1.0</TableCell>
                          <TableCell className="text-muted-foreground text-sm">Highly unpredictable, sporadic demand</TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </div>

                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    These thresholds are fixed in V1. Configurable classification thresholds will be available in a future version.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </section>

        </div>
      </div>
    </div>
  )
}
