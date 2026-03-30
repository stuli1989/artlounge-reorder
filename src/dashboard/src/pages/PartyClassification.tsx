import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchChannelRules, createChannelRule, updateChannelRule, deleteChannelRule } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import { cn } from '@/lib/utils'

const channelColors: Record<string, string> = {
  supplier: 'bg-blue-100 text-blue-700',
  wholesale: 'bg-green-100 text-green-700',
  online: 'bg-purple-100 text-purple-700',
  store: 'bg-amber-100 text-amber-700',
  internal: 'bg-gray-100 text-gray-700',
  ignore: 'bg-red-100 text-red-700',
  unclassified: 'bg-slate-100 text-slate-500',
}

const ruleTypeLabels: Record<string, { label: string; color: string }> = {
  entity: { label: 'Entity', color: 'bg-blue-50 text-blue-600 border-blue-200' },
  sale_order_prefix: { label: 'SO Prefix', color: 'bg-purple-50 text-purple-600 border-purple-200' },
  default: { label: 'Default', color: 'bg-gray-50 text-gray-600 border-gray-200' },
}

const CHANNEL_OPTIONS = ['supplier', 'wholesale', 'online', 'store', 'internal', 'ignore']
const RULE_TYPE_OPTIONS = ['entity', 'sale_order_prefix', 'default']

interface RuleFormState {
  rule_type: string
  match_value: string
  facility_filter: string
  channel: string
  priority: number
}

const DEFAULT_FORM: RuleFormState = {
  rule_type: 'entity',
  match_value: '',
  facility_filter: '',
  channel: 'wholesale',
  priority: 50,
}

export default function PartyClassification() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const isMobile = useIsMobile()
  const isAdmin = user?.role === 'admin'

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<any | null>(null)
  const [form, setForm] = useState<RuleFormState>(DEFAULT_FORM)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const { data: rules, isLoading } = useQuery({
    queryKey: ['channelRules'],
    queryFn: fetchChannelRules,
  })

  const createMutation = useMutation({
    mutationFn: createChannelRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channelRules'] })
      closeDialog()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, any> }) =>
      updateChannelRule(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channelRules'] })
      closeDialog()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteChannelRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channelRules'] })
      setDeletingId(null)
    },
  })

  const openAddDialog = () => {
    setEditingRule(null)
    setForm(DEFAULT_FORM)
    setDialogOpen(true)
  }

  const openEditDialog = (rule: any) => {
    setEditingRule(rule)
    setForm({
      rule_type: (rule.rule_type ?? 'entity') as string,
      match_value: (rule.match_value ?? '') as string,
      facility_filter: (rule.facility_filter ?? '') as string,
      channel: (rule.channel ?? 'wholesale') as string,
      priority: (rule.priority ?? 50) as number,
    })
    setDialogOpen(true)
  }

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingRule(null)
    setForm(DEFAULT_FORM)
  }

  const handleSave = () => {
    const payload = {
      rule_type: form.rule_type,
      match_value: form.match_value,
      facility_filter: form.facility_filter.trim() || null,
      channel: form.channel,
      priority: form.priority,
    }
    if (editingRule) {
      updateMutation.mutate({ id: editingRule.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleDelete = (id: number) => {
    if (deletingId === id) {
      deleteMutation.mutate(id)
    } else {
      setDeletingId(id)
      // Auto-cancel confirmation after 4 seconds
      setTimeout(() => setDeletingId(prev => (prev === id ? null : prev)), 4000)
    }
  }

  const sortedRules = [...(rules ?? [])].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))

  const isSaving = createMutation.isPending || updateMutation.isPending

  // ── Shared Add Rule dialog ──
  const ruleDialog = (
    <Dialog open={dialogOpen} onOpenChange={open => { if (!open) closeDialog() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editingRule ? 'Edit Rule' : 'Add Rule'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label>Rule Type</Label>
            <Select value={form.rule_type} onValueChange={v => setForm(f => ({ ...f, rule_type: v || f.rule_type }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RULE_TYPE_OPTIONS.map(t => (
                  <SelectItem key={t} value={t}>
                    {ruleTypeLabels[t]?.label ?? t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Match Value</Label>
            <Input
              value={form.match_value}
              onChange={e => setForm(f => ({ ...f, match_value: e.target.value }))}
              placeholder="e.g. GRN, PICKLIST, MA-, SO"
              className="font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Facility Filter <span className="text-muted-foreground font-normal">(optional)</span></Label>
            <Input
              value={form.facility_filter}
              onChange={e => setForm(f => ({ ...f, facility_filter: e.target.value }))}
              placeholder="Leave empty for all facilities"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Channel</Label>
            <Select value={form.channel} onValueChange={v => setForm(f => ({ ...f, channel: v || f.channel }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHANNEL_OPTIONS.map(c => (
                  <SelectItem key={c} value={c}>
                    <span className="capitalize">{c}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Priority</Label>
            <Input
              type="number"
              value={form.priority}
              onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))}
              placeholder="50"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <Button variant="outline" className="flex-1" onClick={closeDialog} disabled={isSaving}>
              Cancel
            </Button>
            <Button
              className="flex-1"
              onClick={handleSave}
              disabled={isSaving || !form.match_value.trim() || !form.channel || !form.rule_type}
            >
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )

  // ── Mobile layout ──
  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Channel Rules</h2>
          {isAdmin && (
            <Button size="sm" onClick={openAddDialog}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          )}
        </div>

        <div className="bg-muted/50 border rounded-lg p-4 text-sm text-muted-foreground">
          <p className="font-medium text-foreground mb-1">How channel rules work</p>
          <p>Rules are evaluated top-to-bottom by priority. Entity rules match the transaction type (GRN, PICKLIST, etc.).
          Sale order prefix rules match the start of the order number (MA- for online, SO for wholesale).
          Default rules are the fallback when nothing else matches. Changes trigger an automatic recalculation.</p>
        </div>

        {isLoading ? (
          <div className="space-y-0 -mx-4">
            {Array.from({ length: 5 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : sortedRules.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">No rules configured.</div>
        ) : (
          <div className="-mx-4">
            {sortedRules.map(rule => (
              <MobileListRow
                key={rule.id}
                title={rule.match_value || '(default)'}
                subtitle={`${ruleTypeLabels[rule.rule_type]?.label ?? rule.rule_type} · Priority ${rule.priority}`}
                statusLabel={rule.channel}
                status="ok"
                metrics={rule.facility_filter ? [{ label: 'Facility', value: rule.facility_filter }] : []}
                rightContent={
                  isAdmin ? (
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={e => { e.stopPropagation(); openEditDialog(rule) }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className={cn('h-8 w-8', deletingId === rule.id ? 'text-red-600' : '')}
                        onClick={e => { e.stopPropagation(); handleDelete(rule.id) }}
                        disabled={deleteMutation.isPending && deleteMutation.variables === rule.id}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ) : undefined
                }
              />
            ))}
          </div>
        )}

        {ruleDialog}
      </div>
    )
  }

  // ── Desktop layout ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Channel Rules</h2>
        {isAdmin && (
          <Button onClick={openAddDialog}>
            <Plus className="h-4 w-4 mr-2" />
            Add Rule
          </Button>
        )}
      </div>

      <div className="bg-muted/50 border rounded-lg p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground mb-1">How channel rules work</p>
        <p>Rules are evaluated top-to-bottom by priority. Entity rules match the transaction type (GRN, PICKLIST, etc.).
        Sale order prefix rules match the start of the order number (MA- for online, SO for wholesale).
        Default rules are the fallback when nothing else matches. Changes trigger an automatic recalculation.</p>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : sortedRules.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No rules configured yet.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">Priority</TableHead>
                  <TableHead className="w-[130px]">Type</TableHead>
                  <TableHead>Match Value</TableHead>
                  <TableHead>Facility</TableHead>
                  <TableHead className="w-[120px]">Channel</TableHead>
                  {isAdmin && <TableHead className="w-[100px] text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRules.map(rule => {
                  const typeInfo = ruleTypeLabels[rule.rule_type] ?? { label: rule.rule_type, color: 'bg-gray-50 text-gray-600 border-gray-200' }
                  const isConfirmingDelete = deletingId === rule.id
                  return (
                    <TableRow key={rule.id}>
                      <TableCell>
                        <span className="font-bold">{rule.priority}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn('text-xs', typeInfo.color)}>
                          {typeInfo.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">{rule.match_value || <span className="text-muted-foreground italic">—</span>}</span>
                      </TableCell>
                      <TableCell>
                        {rule.facility_filter
                          ? <span className="text-sm">{rule.facility_filter}</span>
                          : <span className="text-muted-foreground text-sm">All facilities</span>
                        }
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', channelColors[rule.channel] ?? channelColors.unclassified)}>
                          {rule.channel}
                        </Badge>
                      </TableCell>
                      {isAdmin && (
                        <TableCell className="text-right">
                          <div className="flex gap-1 justify-end">
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              onClick={() => openEditDialog(rule)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className={cn(
                                'h-7 w-7 transition-colors',
                                isConfirmingDelete
                                  ? 'bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700'
                                  : 'text-muted-foreground hover:text-destructive'
                              )}
                              onClick={() => handleDelete(rule.id)}
                              disabled={deleteMutation.isPending && deleteMutation.variables === rule.id}
                              title={isConfirmingDelete ? 'Click again to confirm delete' : 'Delete rule'}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {ruleDialog}
    </div>
  )
}
