import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Wallet, Plus, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

export default function WalletPage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState(0);
  const [transactions, setTransactions] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchBalance();
    fetchTransactions();
    if (user?.role === 'admin') {
      fetchAllUsers();
    }
  }, [user]);

  const fetchBalance = async () => {
    try {
      const response = await api.get('/wallet/balance');
      setBalance(response.data.balance);
    } catch (error) {
      console.error('Failed to fetch balance:', error);
    }
  };

  const fetchTransactions = async () => {
    try {
      const response = await api.get('/wallet/transactions');
      setTransactions(response.data);
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
    }
  };

  const fetchAllUsers = async () => {
    try {
      const response = await api.get('/wallet/all-users');
      setAllUsers(response.data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  };

  const handleAddCredits = async (e) => {
    e.preventDefault();
    if (!selectedUserId || !amount) return;

    setLoading(true);
    try {
      await api.post('/wallet/add-credits', {
        user_id: parseInt(selectedUserId),
        amount: parseInt(amount),
        description: description || 'Admin credit addition'
      });
      
      setAmount('');
      setDescription('');
      setSelectedUserId('');
      fetchAllUsers();
      if (parseInt(selectedUserId) === user.id) {
        fetchBalance();
        fetchTransactions();
      }
      alert('Credits added successfully!');
    } catch (error) {
      alert('Failed to add credits: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Wallet</h1>
      </div>

      {/* Balance Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            Current Balance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-4xl font-bold text-blue-600">
            {balance} Credits
          </div>
          {/*<p className="text-sm text-gray-500 mt-2">1 Interview = 1 Credit</p>*/}
        </CardContent>
      </Card>

      {/* Admin: Add Credits */}
      {user?.role === 'admin' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              Add Credits (Admin)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddCredits} className="space-y-4">
              <div>
                <Label>Select User</Label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="w-full border rounded-md p-2"
                  required
                >
                  <option value="">Choose user...</option>
                  {allUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email}) - Balance: {u.wallet_balance} Credits
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label>Credits</Label>
                <Input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Enter credits"
                  required
                />
              </div>
              <div>
                <Label>Description</Label>
                <Input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Reason for credit"
                />
              </div>
              <Button type="submit" disabled={loading}>
                {loading ? 'Adding...' : 'Add Credits'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="text-gray-500">No transactions yet</p>
          ) : (
            <div className="space-y-3">
              {transactions.map((txn) => (
                <div
                  key={txn.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {txn.transaction_type === 'credit' ? (
                      <ArrowUpCircle className="h-5 w-5 text-green-600" />
                    ) : (
                      <ArrowDownCircle className="h-5 w-5 text-red-600" />
                    )}
                    <div>
                      <p className="font-medium">{txn.description}</p>
                      <p className="text-sm text-gray-500">
                        {new Date(txn.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p
                      className={`font-bold ${
                        txn.transaction_type === 'credit'
                          ? 'text-green-600'
                          : 'text-red-600'
                      }`}
                    >
                      {txn.transaction_type === 'credit' ? '+' : '-'}
                      {txn.amount} Credits
                    </p>
                    <p className="text-sm text-gray-500">
                      Balance: {txn.balance_after} Credits
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
