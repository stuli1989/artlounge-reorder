import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchUnclassifiedParties, fetchAllParties, classifyParty } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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

const channelColors: Record<string, string> = {
  supplier: 'bg-blue-100 text-blue-700',
  wholesale: 'bg-green-100 text-green-700',
  online: 'bg-purple-100 text-purple-700',
  store: 'bg-amber-100 text-amber-700',
  internal: 'bg-gray-100 text-gray-700',
  ignore: 'bg-red-100 text-red-700',
  unclassified: 'bg-slate-100 text-slate-500',
}

type Tab = 'unclassified' | 'all'

export default function PartyClassification() {
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [tab, setTab] = useState<Tab>('unclassified')
  const [selections, setSelections] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [channelFilter, setChannelFilter] = useState<string>('all')
  const [editingParty, setEditingParty] = useState<string | null>(null)

  const { data: unclassifiedParties, isLoading: loadingUnclassified } = useQuery({
    queryKey: ['unclassifiedParties'],
    queryFn: fetchUnclassifiedParties,
  })

  const { data: allParties, isLoading: loadingAll } = useQuery({
    queryKey: ['allParties'],
    queryFn: () => fetchAllParties(),
    enabled: tab === 'all',
  })

  const isLoading = tab === 'unclassified' ? loadingUnclassified : loadingAll
  const parties = tab === 'unclassified' ? unclassifiedParties : allParties

  // Filter parties
  const filteredParties = (parties || []).filter(p => {
    if (search && !p.tally_name.toLowerCase().includes(search.toLowerCase())) return false
    if (tab === 'all' && channelFilter !== 'all' && (p as { channel?: string }).channel !== channelFilter) return false
    return true
  })

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
      queryClient.invalidateQueries({ queryKey: ['allParties'] })
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
    } catch (err) {
      console.error("Failed to classify party:", err)
      alert("Failed to save classification. Please try again.")
    } finally {
      setSaving(null)
    }
  }

  const unclassifiedCount = unclassifiedParties?.length ?? 0

  // ── Tab bar (shared between mobile and desktop) ──
  const tabBar = (
    <div className="flex gap-1 bg-muted p-1 rounded-lg">
      <button
        onClick={() => { setTab('unclassified'); setSearch(''); setChannelFilter('all') }}
        className={cn(
          'flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
          tab === 'unclassified' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'
        )}
      >
        Needs Classification{unclassifiedCount > 0 && ` (${unclassifiedCount})`}
      </button>
      <button
        onClick={() => { setTab('all'); setSearch(''); setChannelFilter('all') }}
        className={cn(
          'flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
          tab === 'all' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'
        )}
      >
        All Parties
      </button>
    </div>
  )

  // ── Channel badge ──
  const channelBadge = (ch: string) => (
    <Badge className={cn('capitalize', channelColors[ch] || channelColors.unclassified)}>
      {ch}
    </Badge>
  )

  // ── Mobile ──
  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        <h2 className="text-lg font-semibold">Party Classification</h2>
        {tabBar}

        {success && (
          <Alert className="bg-green-50 border-green-200">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">Classified successfully</AlertDescription>
          </Alert>
        )}

        {/* Search + channel filter */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search parties..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 h-10"
            />
          </div>
          {tab === 'all' && (
            <Select value={channelFilter} onValueChange={v => { if (v) setChannelFilter(v) }}>
              <SelectTrigger className="w-[130px] h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All channels</SelectItem>
                {channelOptions.map(o => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
                <SelectItem value="unclassified">Unclassified</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Party list */}
        {isLoading ? (
          <div className="space-y-0 -mx-4">
            {Array.from({ length: 5 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : filteredParties.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {tab === 'unclassified' && unclassifiedCount === 0 ? 'All parties classified!' : 'No parties match filters'}
          </div>
        ) : (
          <div className="-mx-4">
            {filteredParties.map(p => {
              const currentChannel = (p as { channel?: string }).channel || 'unclassified'
              return (
                <MobileListRow
                  key={p.tally_name}
                  title={p.tally_name}
                  subtitle={p.tally_parent || undefined}
                  status={currentChannel === 'unclassified' ? 'no_data' : 'ok'}
                  statusLabel={selections[p.tally_name] || currentChannel}
                  metrics={[
                    { label: 'Txns', value: String(p.transaction_count) },
                  ]}
                  onClick={() => {
                    if (tab === 'all' && currentChannel !== 'unclassified') {
                      setSelections(s => ({ ...s, [p.tally_name]: currentChannel }))
                    }
                    setEditingParty(p.tally_name)
                  }}
                />
              )
            })}
          </div>
        )}

        {/* Classification BottomSheet */}
        <BottomSheet
          open={!!editingParty}
          onOpenChange={open => { if (!open) setEditingParty(null) }}
          title={tab === 'all' ? 'Reclassify Party' : 'Classify Party'}
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

  // ── Desktop ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Party Classification</h2>
        <div className="w-[360px]">{tabBar}</div>
      </div>

      {success && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            Party classified successfully
          </AlertDescription>
        </Alert>
      )}

      {/* Search + channel filter */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by party name..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        {tab === 'all' && (
          <Select value={channelFilter} onValueChange={v => { if (v) setChannelFilter(v) }}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All channels</SelectItem>
              {channelOptions.map(o => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
              <SelectItem value="unclassified">Unclassified</SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            {tab === 'unclassified'
              ? `${filteredParties.length} parties need classification`
              : `${filteredParties.length} parties${channelFilter !== 'all' ? ` (${channelFilter})` : ''}`
            }
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : filteredParties.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {tab === 'unclassified' && unclassifiedCount === 0
                ? 'All parties are classified. Nothing to do!'
                : 'No parties match filters'}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Party Name</TableHead>
                  <TableHead>Tally Group</TableHead>
                  {tab === 'all' && <TableHead>Current</TableHead>}
                  <TableHead className="text-right">Transactions</TableHead>
                  <TableHead className="w-[200px]">{tab === 'all' ? 'Change To' : 'Channel'}</TableHead>
                  <TableHead className="w-[80px]">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredParties.map(p => {
                  const currentChannel = (p as { channel?: string }).channel || 'unclassified'
                  const selected = selections[p.tally_name]
                  const changed = selected && selected !== currentChannel
                  return (
                    <TableRow key={p.tally_name} className={changed ? 'bg-amber-50/50' : undefined}>
                      <TableCell className="font-medium">{p.tally_name}</TableCell>
                      <TableCell className="text-muted-foreground">{p.tally_parent || '-'}</TableCell>
                      {tab === 'all' && <TableCell>{channelBadge(currentChannel)}</TableCell>}
                      <TableCell className="text-right">{p.transaction_count}</TableCell>
                      <TableCell>
                        <Select
                          value={selected || (tab === 'all' ? currentChannel : '')}
                          onValueChange={v => { if (v) setSelections(s => ({ ...s, [p.tally_name]: v })) }}
                        >
                          <SelectTrigger className={changed ? 'border-amber-400 ring-1 ring-amber-200' : ''}>
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
                          variant={changed ? 'default' : 'outline'}
                          onClick={() => handleSave(p.tally_name)}
                          disabled={tab === 'unclassified' ? !selected : !changed}
                        >
                          {saving === p.tally_name ? '...' : 'Save'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
