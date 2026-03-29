import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSuppliers, createSupplier, updateSupplier, deleteSupplier } from '@/lib/api'
import type { Supplier } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Plus, Pencil, Trash2, X, Check } from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import { BottomSheet } from '@/components/mobile/BottomSheet'

type FormData = Omit<Supplier, 'id'> & { id?: number }

const emptyForm: FormData = {
  name: '', tally_party: '', lead_time_sea: null, lead_time_air: null,
  lead_time_default: 90, currency: 'USD', min_order_value: null,
  typical_order_months: null, notes: '', buffer_override: null,
  
}

export default function SupplierManagement() {
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<FormData>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)

  const { data: suppliers, isLoading } = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
  })

  const handleSubmit = async () => {
    setError(null)
    if (!form.name.trim()) { setError('Name is required'); return }

    try {
      if (editingId) {
        await updateSupplier(editingId, form)
      } else {
        await createSupplier(form)
      }
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      setShowForm(false)
      setEditingId(null)
      setForm(emptyForm)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    }
  }

  const handleEdit = (s: Supplier) => {
    setForm({ ...s })
    setEditingId(s.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    setError(null)
    try {
      await deleteSupplier(id)
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      setDeleteConfirmId(null)
    } catch {
      setError('Cannot delete — supplier is in use')
      setDeleteConfirmId(null)
    }
  }

  const updateField = (field: string, value: string | number | boolean | null) => {
    setForm(f => ({ ...f, [field]: value }))
  }

  const renderForm = () => (
    <div className="space-y-4">
      <div className={isMobile ? 'space-y-3' : 'grid grid-cols-3 gap-4'}>
        <div className="space-y-1">
          <Label>Name *</Label>
          <Input value={form.name} onChange={e => updateField('name', e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>UC Party</Label>
          <Input value={form.tally_party} onChange={e => updateField('tally_party', e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Currency</Label>
          <Input value={form.currency} onChange={e => updateField('currency', e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Sea Lead Time (days)</Label>
          <Input type="number" inputMode="numeric" min={1} value={form.lead_time_sea ?? ''} onChange={e => updateField('lead_time_sea', e.target.value ? Number(e.target.value) : null)} />
        </div>
        <div className="space-y-1">
          <Label>Air Lead Time (days)</Label>
          <Input type="number" inputMode="numeric" min={1} value={form.lead_time_air ?? ''} onChange={e => updateField('lead_time_air', e.target.value ? Number(e.target.value) : null)} />
        </div>
        <div className="space-y-1">
          <Label>Default Lead Time (days)</Label>
          <Input type="number" inputMode="numeric" min={1} value={form.lead_time_default} onChange={e => updateField('lead_time_default', Number(e.target.value))} />
        </div>
        <div className="space-y-1">
          <Label>Buffer Override</Label>
          <Input
            type="number"
            inputMode="decimal"
            step="0.1"
            min="0.1"
            placeholder="Leave empty for default"
            value={form.buffer_override ?? ''}
            onChange={e => updateField('buffer_override', e.target.value ? parseFloat(e.target.value) : null)}
          />
        </div>
        <div className="space-y-1">
          <Label>Order Coverage (months)</Label>
          <Input
            type="number"
            inputMode="numeric"
            min="1"
            placeholder="Auto"
            value={form.typical_order_months ?? ''}
            onChange={e => updateField('typical_order_months', e.target.value ? Number(e.target.value) : null)}
          />
          <p className="text-xs text-muted-foreground">How many months of stock each order covers. Leave empty to auto-calculate from lead time.</p>
        </div>
      </div>
      <div className="space-y-1">
        <Label>Notes</Label>
        <Input value={form.notes} onChange={e => updateField('notes', e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button className="flex-1" onClick={handleSubmit}><Check className="h-4 w-4 mr-1" /> Save</Button>
        <Button variant="outline" className="flex-1" onClick={() => { setShowForm(false); setEditingId(null); setError(null) }}>
          <X className="h-4 w-4 mr-1" /> Cancel
        </Button>
      </div>
    </div>
  )

  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Suppliers</h2>
          <Button size="sm" onClick={() => { setForm(emptyForm); setEditingId(null); setShowForm(true) }}>
            <Plus className="h-4 w-4 mr-1" /> Add
          </Button>
        </div>

        {error && !showForm && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Supplier list */}
        {isLoading ? (
          <div className="space-y-0 -mx-4">
            {Array.from({ length: 4 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : (suppliers || []).length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">No suppliers configured</div>
        ) : (
          <div className="-mx-4">
            {(suppliers || []).map(s => (
              <MobileListRow
                key={s.id}
                title={s.name}
                subtitle={s.tally_party || undefined}
                metrics={[
                  { label: 'Lead', value: `${s.lead_time_default}d` },
                  { label: 'Coverage', value: s.typical_order_months != null ? `${s.typical_order_months}mo` : 'auto' },
                  { label: 'Buffer', value: s.buffer_override != null ? `${s.buffer_override}x` : '\u2014' },
                ]}
                onClick={() => handleEdit(s)}
              />
            ))}
          </div>
        )}

        {/* Edit/Add BottomSheet */}
        <BottomSheet
          open={showForm}
          onOpenChange={open => { if (!open) { setShowForm(false); setEditingId(null); setError(null) } }}
          title={editingId ? 'Edit Supplier' : 'New Supplier'}
        >
          {renderForm()}
          {editingId && (
            <Button
              variant="ghost"
              className="w-full mt-2 text-red-600"
              onClick={() => { setShowForm(false); setDeleteConfirmId(editingId) }}
            >
              <Trash2 className="h-4 w-4 mr-1" /> Delete Supplier
            </Button>
          )}
        </BottomSheet>

        {/* Delete confirmation BottomSheet */}
        <BottomSheet
          open={deleteConfirmId !== null}
          onOpenChange={open => { if (!open) setDeleteConfirmId(null) }}
          title="Delete Supplier?"
        >
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete this supplier? This cannot be undone.
            </p>
            <div className="flex gap-2">
              <Button variant="destructive" className="flex-1" onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}>
                Delete
              </Button>
              <Button variant="outline" className="flex-1" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </Button>
            </div>
          </div>
        </BottomSheet>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Supplier Management</h2>
        {!showForm && (
          <Button onClick={() => { setForm(emptyForm); setEditingId(null); setShowForm(true) }}>
            <Plus className="h-4 w-4 mr-1" /> Add Supplier
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{editingId ? 'Edit Supplier' : 'New Supplier'}</CardTitle>
          </CardHeader>
          <CardContent>
            {renderForm()}
          </CardContent>
        </Card>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">Loading...</div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>UC Party</TableHead>
                <TableHead className="text-right">Sea (days)</TableHead>
                <TableHead className="text-right">Air (days)</TableHead>
                <TableHead className="text-right">Default (days)</TableHead>
                <TableHead className="text-right">Buffer</TableHead>
                <TableHead className="text-right">Coverage</TableHead>
                <TableHead>Backdate</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(suppliers || []).map(s => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell className="text-muted-foreground">{s.tally_party}</TableCell>
                  <TableCell className="text-right">{s.lead_time_sea ?? '-'}</TableCell>
                  <TableCell className="text-right">{s.lead_time_air ?? '-'}</TableCell>
                  <TableCell className="text-right">{s.lead_time_default}</TableCell>
                  <TableCell className="text-right">
                    {s.buffer_override != null ? `${s.buffer_override}x` : '\u2014'}
                  </TableCell>
                  <TableCell className="text-right">
                    {s.typical_order_months != null
                      ? `${s.typical_order_months}mo (${s.typical_order_months * 30}d)`
                      : <span className="text-muted-foreground">auto</span>}
                  </TableCell>
                  <TableCell>
                    
                  </TableCell>
                  <TableCell>{s.currency}</TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate">{s.notes}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(s)}>
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => {
                        if (window.confirm(`Delete supplier "${s.name}"?`)) {
                          handleDelete(s.id)
                        }
                      }}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {(suppliers || []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                    No suppliers configured
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
