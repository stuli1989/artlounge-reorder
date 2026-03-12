import { useQuery } from '@tanstack/react-query'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { fetchTransactions } from '@/lib/api'

interface Props {
  categoryName: string
  stockItemName: string
}

const channelColors: Record<string, string> = {
  wholesale: 'bg-blue-100 text-blue-700',
  online: 'bg-purple-100 text-purple-700',
  store: 'bg-green-100 text-green-700',
  supplier: 'bg-orange-100 text-orange-700',
  internal: 'bg-gray-100 text-gray-500',
  ignore: 'bg-gray-50 text-gray-400',
}

export default function TransactionHistory({ categoryName, stockItemName }: Props) {
  const { data: transactions, isLoading } = useQuery({
    queryKey: ['transactions', categoryName, stockItemName],
    queryFn: () => fetchTransactions(categoryName, stockItemName, 20),
  })

  if (isLoading) return <div className="py-4 text-center text-muted-foreground">Loading transactions...</div>
  if (!transactions?.length) return <div className="py-4 text-center text-muted-foreground">No transactions found</div>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[90px]">Date</TableHead>
          <TableHead>Party</TableHead>
          <TableHead>Type</TableHead>
          <TableHead className="w-[80px]">Voucher #</TableHead>
          <TableHead className="w-[70px] text-right">Qty In</TableHead>
          <TableHead className="w-[70px] text-right">Qty Out</TableHead>
          <TableHead className="w-[80px]">Channel</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {transactions.map((t, i) => (
          <TableRow key={i}>
            <TableCell className="text-xs">{new Date(t.txn_date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}</TableCell>
            <TableCell className="text-xs max-w-[200px] truncate">{t.party_name}</TableCell>
            <TableCell className="text-xs">{t.voucher_type}</TableCell>
            <TableCell className="text-xs">{t.voucher_number}</TableCell>
            <TableCell className="text-xs text-right text-green-600">{t.is_inward ? t.quantity : ''}</TableCell>
            <TableCell className="text-xs text-right text-red-600">{!t.is_inward ? t.quantity : ''}</TableCell>
            <TableCell>
              <Badge variant="outline" className={`text-xs ${channelColors[t.channel] || ''}`}>
                {t.channel}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
