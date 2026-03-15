import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchUnclassifiedParties, classifyParty } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { CheckCircle, Search } from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import { BottomSheet } from '@/components/mobile/BottomSheet'
import { cn } from '@/lib/utils'

const channelOptions = [
  { value: 'supplier', label: 'Supplier', desc: 'International brand you import from', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  { value: 'wholesale', label: 'Wholesale', desc: 'Shops/distributors that buy from you', color: 'bg-green-100 text-green-700 border-green-200' },
  { value: 'online', label: 'Online', desc: 'E-commerce platform', color: 'bg-purple-100 text-purple-700 border-purple-200' },
  { value: 'store', label: 'Store', desc: 'Own retail store', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  { value: 'internal', label: 'Internal', desc: 'Accounting entries', color: 'bg-gray-100 text-gray-700 border-gray-200' },
  { value: 'ignore', label: 'Ignore', desc: 'System adjustments', color: 'bg-red-100 text-red-700 border-red-200' },
]

export default function PartyClassification() {
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [selections, setSelections] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [editingParty, setEditingParty] = useState<string | null>(null)

  const { data: parties, isLoading } = useQuery({
    queryKey: ['unclassifiedParties'],
    queryFn: fetchUnclassifiedParties,
  })

  const filteredParties = search
    ? (parties || []).filter(p => p.tally_name.toLowerCase().includes(search.toLowerCase()))
    : (parties || [])

  const handleSave = async (partyName: string) => {
    const channel = selections[partyName]
    if (!channel) return

    setSaving(partyName)
    try {
      await classifyParty(partyName, channel)
      setSuccess(partyName)
      setTimeout(() => setSuccess(null), 2000)
      setEditingParty(null)
      queryClient.invalidateQueries({ queryKey: ['unclassifiedParties'] })
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
    } finally {
      setSaving(null)
    }
  }

  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        <h2 className="text-lg font-semibold">Party Classification</h2>
        <p className="text-sm text-muted-foreground">{parties?.length ?? '...'} parties need classification</p>

        {success && (
          <Alert className="bg-green-50 border-green-200">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">Classified successfully</AlertDescription>
          </Alert>
        )}

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search parties..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 h-10"
          />
        </div>

        {/* Party list */}
        {isLoading ? (
          <div className="space-y-0 -mx-4">
            {Array.from({ length: 5 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : filteredParties.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {parties?.length === 0 ? 'All parties classified!' : 'No parties match search'}
          </div>
        ) : (
          <div className="-mx-4">
            {filteredParties.map(p => (
              <MobileListRow
                key={p.tally_name}
                title={p.tally_name}
                subtitle={p.tally_parent || undefined}
                status={selections[p.tally_name] ? 'ok' : 'no_data'}
                statusLabel={selections[p.tally_name] || 'Unclassified'}
                metrics={[
                  { label: 'Txns', value: String(p.transaction_count) },
                ]}
                onClick={() => setEditingParty(p.tally_name)}
              />
            ))}
          </div>
        )}

        {/* Classification BottomSheet */}
        <BottomSheet
          open={!!editingParty}
          onOpenChange={open => { if (!open) setEditingParty(null) }}
          title="Classify Party"
        >
          {editingParty && (
            <div className="space-y-4">
              <div>
                <p className="font-medium text-sm">{editingParty}</p>
                <p className="text-xs text-muted-foreground">
                  {(parties || []).find(p => p.tally_name === editingParty)?.tally_parent || 'No group'}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {channelOptions.map(o => (
                  <button
                    key={o.value}
                    onClick={() => setSelections(s => ({ ...s, [editingParty]: o.value }))}
                    className={cn(
                      'border rounded-lg px-3 py-3 text-left transition-colors',
                      selections[editingParty] === o.value
                        ? `${o.color} border-2 font-medium`
                        : 'border-border hover:bg-muted/50'
                    )}
                  >
                    <div className="text-sm font-medium">{o.label}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{o.desc}</div>
                  </button>
                ))}
              </div>

              <Button
                className="w-full"
                onClick={() => handleSave(editingParty)}
                disabled={!selections[editingParty] || saving === editingParty}
              >
                {saving === editingParty ? 'Saving...' : 'Save Classification'}
              </Button>
            </div>
          )}
        </BottomSheet>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Party Classification</h2>

      {success && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            Party classified successfully
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            {parties?.length ?? '...'} parties need classification
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : parties?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              All parties are classified. Nothing to do!
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Party Name</TableHead>
                  <TableHead>Tally Group</TableHead>
                  <TableHead className="text-right">Transactions</TableHead>
                  <TableHead className="w-[200px]">Channel</TableHead>
                  <TableHead className="w-[80px]">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(parties || []).map(p => (
                  <TableRow key={p.tally_name}>
                    <TableCell className="font-medium">{p.tally_name}</TableCell>
                    <TableCell className="text-muted-foreground">{p.tally_parent || '-'}</TableCell>
                    <TableCell className="text-right">{p.transaction_count}</TableCell>
                    <TableCell>
                      <Select
                        value={selections[p.tally_name] || ''}
                        onValueChange={v => { if (v) setSelections(s => ({ ...s, [p.tally_name]: v })) }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select channel..." />
                        </SelectTrigger>
                        <SelectContent>
                          {channelOptions.map(o => (
                            <SelectItem key={o.value} value={o.value}>
                              {o.label} — {o.desc}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        onClick={() => handleSave(p.tally_name)}
                        disabled={!selections[p.tally_name] || saving === p.tally_name}
                      >
                        {saving === p.tally_name ? '...' : 'Save'}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
