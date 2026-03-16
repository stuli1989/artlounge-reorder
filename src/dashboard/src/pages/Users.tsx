import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchUsers, createUser, updateUser, resetUserPassword } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/contexts/AuthContext'
import { UserCog } from 'lucide-react'

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const { data: users = [], isLoading } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('viewer')
  const [createError, setCreateError] = useState('')

  const [resetId, setResetId] = useState<number | null>(null)
  const [resetPw, setResetPw] = useState('')

  const createMut = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowCreate(false)
      setNewUsername('')
      setNewPassword('')
      setNewRole('viewer')
      setCreateError('')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(msg || 'Failed to create user')
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { role?: string; is_active?: boolean } }) => updateUser(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const resetMut = useMutation({
    mutationFn: ({ id, pw }: { id: number; pw: string }) => resetUserPassword(id, pw),
    onSuccess: () => { setResetId(null); setResetPw('') },
  })

  if (currentUser?.role !== 'admin') return <p className="text-muted-foreground">Admin access required.</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <UserCog className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Users</h2>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          {showCreate ? 'Cancel' : '+ Add User'}
        </button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Create New User</CardTitle></CardHeader>
          <CardContent>
            <form
              onSubmit={e => { e.preventDefault(); createMut.mutate({ username: newUsername, password: newPassword, role: newRole }) }}
              className="flex flex-wrap items-end gap-3"
            >
              <div className="space-y-1">
                <label className="text-xs font-medium">Username</label>
                <input
                  value={newUsername} onChange={e => setNewUsername(e.target.value)}
                  className="flex h-9 w-40 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  required minLength={2}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Password</label>
                <input
                  type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  className="flex h-9 w-40 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  required minLength={8}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Role</label>
                <select
                  value={newRole} onChange={e => setNewRole(e.target.value)}
                  className="flex h-9 w-32 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="viewer">Viewer</option>
                  <option value="purchaser">Purchaser</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <button
                type="submit" disabled={createMut.isPending}
                className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {createMut.isPending ? 'Creating...' : 'Create'}
              </button>
            </form>
            {createError && <p className="text-sm text-red-600 mt-2">{createError}</p>}
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading users...</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Username</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Role</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Status</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Last Login</th>
                  <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u: Record<string, unknown>) => (
                  <tr key={u.id as number} className="border-b last:border-0">
                    <td className="px-4 py-2.5 font-medium">{u.username as string}</td>
                    <td className="px-4 py-2.5">
                      <select
                        value={u.role as string}
                        onChange={e => updateMut.mutate({ id: u.id as number, data: { role: e.target.value } })}
                        className="text-xs rounded border px-2 py-1 bg-background"
                        disabled={u.id === currentUser?.id}
                      >
                        <option value="viewer">Viewer</option>
                        <option value="purchaser">Purchaser</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge className={u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {u.last_login
                        ? new Date(u.last_login as string).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                        : 'Never'}
                    </td>
                    <td className="px-4 py-2.5 text-right space-x-2">
                      <button
                        onClick={() => setResetId(u.id as number)}
                        className="text-xs text-primary hover:underline"
                      >
                        Reset Password
                      </button>
                      {u.id !== currentUser?.id && (
                        <button
                          onClick={() => updateMut.mutate({ id: u.id as number, data: { is_active: !(u.is_active as boolean) } })}
                          className={`text-xs ${u.is_active ? 'text-red-600' : 'text-green-600'} hover:underline`}
                        >
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Reset password modal */}
      {resetId !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 w-full max-w-sm space-y-4 shadow-lg">
            <h3 className="font-semibold">Reset Password</h3>
            <input
              type="password" value={resetPw} onChange={e => setResetPw(e.target.value)}
              placeholder="New password (min 8 chars)"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              minLength={8}
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setResetId(null); setResetPw('') }} className="px-3 py-1.5 text-sm rounded border hover:bg-muted">Cancel</button>
              <button
                onClick={() => resetMut.mutate({ id: resetId, pw: resetPw })}
                disabled={resetPw.length < 8 || resetMut.isPending}
                className="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {resetMut.isPending ? 'Resetting...' : 'Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
