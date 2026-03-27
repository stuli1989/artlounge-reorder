import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Check, HelpCircle, X, ArrowRight } from 'lucide-react'
import type { SkuMatchResult, SkuMatchSummary } from '@/lib/types'

interface SkuMatchReviewProps {
  matches: SkuMatchResult[]
  summary: SkuMatchSummary
  onConfirm: (acceptedNames: string[]) => void
  onBack: () => void
}

export default function SkuMatchReview({ matches, summary, onConfirm, onBack }: SkuMatchReviewProps) {
  const handleConfirm = () => {
    const accepted = matches
      .filter(m => m.matched_name)
      .map(m => m.matched_name!)
    onConfirm(accepted)
  }

  const matchedCount = summary.exact + summary.fuzzy

  return (
    <div className="space-y-4">
      {/* Summary badges */}
      <div className="flex gap-3">
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          <Check className="h-3 w-3 mr-1" /> {summary.exact} exact
        </Badge>
        {summary.fuzzy > 0 && (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
            <HelpCircle className="h-3 w-3 mr-1" /> {summary.fuzzy} fuzzy
          </Badge>
        )}
        {summary.unmatched > 0 && (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <X className="h-3 w-3 mr-1" /> {summary.unmatched} unmatched
          </Badge>
        )}
      </div>

      {summary.unmatched > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertDescription className="text-amber-800 text-sm">
            {summary.unmatched} SKU{summary.unmatched !== 1 ? 's' : ''} could not be matched.
            Unmatched items will be skipped. Check spelling or use exact SKU codes.
          </AlertDescription>
        </Alert>
      )}

      {/* Match table — only show fuzzy and unmatched rows */}
      {(summary.fuzzy > 0 || summary.unmatched > 0) && (
        <div className="border rounded-lg max-h-64 overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Your Input</TableHead>
                <TableHead className="w-10"></TableHead>
                <TableHead>Matched To</TableHead>
                <TableHead className="w-20">Match</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matches
                .filter(m => m.match_type !== 'exact')
                .map((m, i) => (
                <TableRow key={i} className={m.match_type === 'unmatched' ? 'opacity-50' : ''}>
                  <TableCell className="text-sm truncate max-w-[200px]">{m.input_name}</TableCell>
                  <TableCell>
                    {m.matched_name ? <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                  </TableCell>
                  <TableCell className="text-sm truncate max-w-[200px]">
                    {m.matched_name ?? <span className="text-red-500 italic">No match</span>}
                  </TableCell>
                  <TableCell>
                    {m.match_type === 'fuzzy' && (
                      <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700">
                        {Math.round((m.similarity ?? 0) * 100)}%
                      </Badge>
                    )}
                    {m.match_type === 'unmatched' && (
                      <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700">
                        miss
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* All exact — just confirm */}
      {summary.fuzzy === 0 && summary.unmatched === 0 && (
        <p className="text-sm text-muted-foreground">
          All {summary.exact} SKUs matched exactly. Ready to build PO.
        </p>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <Button onClick={handleConfirm} disabled={matchedCount === 0}>
          Build PO with {matchedCount} item{matchedCount !== 1 ? 's' : ''}
        </Button>
      </div>
    </div>
  )
}
