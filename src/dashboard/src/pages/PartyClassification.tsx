import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchUnclassifiedParties, classifyParty } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { CheckCircle } from 'lucide-react'

const channelOptions = [
  { value: 'supplier', label: 'Supplier', desc: 'International brand you import from' },
  { value: 'wholesale', label: 'Wholesale', desc: 'Shops/distributors that buy from you' },
  { value: 'online', label: 'Online', desc: 'E-commerce platform' },
  { value: 'store', label: 'Store', desc: 'Own retail store' },
  { value: 'internal', label: 'Internal', desc: 'Accounting entries' },
  { value: 'ignore', label: 'Ignore', desc: 'System adjustments' },
]

export default function PartyClassification() {
  const queryClient = useQueryClient()
  const [selections, setSelections] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const { data: parties, isLoading } = useQuery({
    queryKey: ['unclassifiedParties'],
    queryFn: fetchUnclassifiedParties,
  })

  const handleSave = async (partyName: string) => {
    const channel = selections[partyName]
    if (!channel) return

    setSaving(partyName)
    try {
      await classifyParty(partyName, channel)
      setSuccess(partyName)
      setTimeout(() => setSuccess(null), 2000)
      queryClient.invalidateQueries({ queryKey: ['unclassifiedParties'] })
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
    } finally {
      setSaving(null)
    }
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
