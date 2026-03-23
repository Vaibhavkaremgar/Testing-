import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Wallet, ArrowUpCircle, ArrowDownCircle, CreditCard, TrendingUp, Minus, Download } from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const PAYMENT_METHODS = [
  { id: 'razorpay', name: 'Razorpay', icon: CreditCard, color: 'text-blue-600' },
];

export default function WalletPage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState(0);
  const [transactions, setTransactions] = useState([]);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [creditAmount, setCreditAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [allUsers, setAllUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [manualCredits, setManualCredits] = useState('');
  const [manualLoading, setManualLoading] = useState(false);
  const [showLowCreditModal, setShowLowCreditModal] = useState(false);

  const getStats = () => {
    const totalCredits = transactions
      .filter(t => t.transaction_type === 'credit')
      .reduce((sum, t) => sum + t.amount, 0);

    const usedCredits = transactions
      .filter(t => t.transaction_type === 'debit')
      .reduce((sum, t) => sum + t.amount, 0);

    return { totalCredits, usedCredits, remainingCredits: balance };
  };

  const { totalCredits, usedCredits, remainingCredits } = getStats();

  useEffect(() => {
    fetchBalance();
    fetchTransactions();
    if (user?.role === 'admin') fetchAllUsers();
  }, [user]);

  const fetchBalance = async () => {
    try {
      const response = await api.get('/wallet/balance');
      const bal = response.balance || 0;
      setBalance(bal);
      if (user?.role === 'admin' && bal <= 10 && !sessionStorage.getItem('lowCreditAlertShown')) {
        sessionStorage.setItem('lowCreditAlertShown', 'true');
        setShowLowCreditModal(true);
      }
    } catch (error) {
      console.error('Failed to fetch balance:', error);
      setBalance(0);
    }
  };

  const fetchTransactions = async () => {
    try {
      const response = await api.get('/wallet/transactions');
      setTransactions(Array.isArray(response) ? response : []);
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
      setTransactions([]);
    }
  };

  const fetchAllUsers = async () => {
    try {
      const response = await api.get('/wallet/all-users');
      setAllUsers(Array.isArray(response) ? response : []);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  };

  const handleAddCreditsManually = async () => {
    if (!selectedUser) return alert('Please select a user');
    if (!manualCredits || manualCredits <= 0) return alert('Please enter a valid credit amount');
    setManualLoading(true);
    try {
      await api.post('/wallet/add-credits', {
        user_id: selectedUser,
        amount: parseInt(manualCredits),
        description: 'Manual credit by admin'
      });
      alert(`Successfully added ${manualCredits} credits!`);
      setSelectedUser('');
      setManualCredits('');
      fetchBalance();
      fetchTransactions();
    } catch (error) {
      alert('Failed to add credits: ' + error.message);
    } finally {
      setManualLoading(false);
    }
  };

  const handleDownloadInvoice = (txn) => {
    const invoiceContent = `
INVOICE
========================================
Transaction ID: ${txn.id}
Date: ${new Date(txn.created_at).toLocaleDateString()}
Description: ${txn.description}
Credits: ${txn.amount}
Amount Paid: $${txn.price_paid || 0}
Payment Method: ${txn.payment_method || 'N/A'}
Status: ${txn.status || 'completed'}
========================================
    `;
    const blob = new Blob([invoiceContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice_${txn.id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleBuyCredits = async () => {
    if (!selectedPayment) {
      alert('Please select a payment method');
      return;
    }

    if (!creditAmount || creditAmount <= 0) {
      alert('Please enter a valid amount');
      return;
    }

    const credits = parseInt(creditAmount);
    const price = parseInt(creditAmount);

    setLoading(true);
    try {
      const orderResponse = await api.post('/wallet/create-order', {
        credits: credits,
        payment_method: selectedPayment
      });

      await api.post('/wallet/payment-success', {
        order_id: orderResponse.order_id,
        transaction_id: `TXN_${Date.now()}`,
        credits: credits,
        payment_method: selectedPayment,
        amount_paid: price
      });

      alert(`Successfully purchased ${credits} credits!`);
      setSelectedPayment(null);
      setCreditAmount('');
      fetchBalance();
      fetchTransactions();
    } catch (error) {
      alert('Payment failed: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Wallet</h1>
      </div>

      {/* Low Credit Modal */}
      {showLowCreditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-yellow-100 p-2 rounded-full">
                <Wallet className="h-6 w-6 text-yellow-600" />
              </div>
              <h2 className="text-lg font-bold text-gray-900">Low Credits Warning</h2>
            </div>
            <p className="text-gray-600 text-sm mb-4">
              Your wallet balance is only <span className="font-bold text-red-600">{balance} credits</span>. Please recharge to continue using interview services.
            </p>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setShowLowCreditModal(false)}>Dismiss</Button>
              <Button className="flex-1" onClick={() => { setShowLowCreditModal(false); document.getElementById('creditAmount')?.focus(); }}>Recharge Now</Button>
            </div>
          </div>
        </div>
      )}

      {/* Wallet Balance Card */}
      <Card className="bg-gradient-to-r from-blue-500 to-blue-600 text-white">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm opacity-90">Wallet Balance</p>
              <h2 className="text-4xl font-bold mt-2">{remainingCredits} Credits</h2>
            </div>
            <Wallet className="h-16 w-16 opacity-20" />
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Credits</CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCredits}</div>
            <p className="text-xs text-muted-foreground mt-1">All time purchased</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Credits Used</CardTitle>
            <Minus className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{usedCredits}</div>
            <p className="text-xs text-muted-foreground mt-1">Total consumed</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Remaining Credits</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{remainingCredits}</div>
            <p className="text-xs text-muted-foreground mt-1">Available now</p>
          </CardContent>
        </Card>
      </div>

      {/* Admin: Add Credits Manually */}
      {user?.role === 'admin' && (
        <Card>
          <CardHeader>
            <CardTitle>Add Credits Manually</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/*<div>
              <Label>Select User</Label>
              <select
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
                className="mt-2 w-full border rounded-md px-3 py-2 text-sm bg-background"
              >
                <option value="">-- Select a user --</option>
                {allUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
            </div>*/}
            <div>
              <Label>Credits to Add</Label>
              <Input
                type="number"
                placeholder="Enter credits"
                value={manualCredits}
                onChange={(e) => setManualCredits(e.target.value)}
                min="1"
                className="mt-2"
              />
            </div>
            <Button onClick={handleAddCreditsManually} disabled={manualLoading} className="w-full">
              {manualLoading ? 'Adding...' : 'Add Credits'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Buy Credits */}
      <Card>
        <CardHeader>
          <CardTitle>Buy Credits</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="creditAmount">Enter Amount</Label>
            <Input
              id="creditAmount"
              type="number"
              placeholder="Enter amount"
              value={creditAmount}
              onChange={(e) => setCreditAmount(e.target.value)}
              min="1"
              className="mt-2"
            />
            {creditAmount && (
              <p className="text-sm text-gray-500 mt-2">
                You will get {creditAmount} credits ($1 per credit)
              </p>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium mb-3">Select Payment Method</h3>
            <div className="space-y-3">
              {PAYMENT_METHODS.map((method) => {
                const Icon = method.icon;
                return (
                  <div
                    key={method.id}
                    onClick={() => setSelectedPayment(method.id)}
                    className={`p-4 border-2 rounded-lg cursor-pointer transition-all flex items-center justify-between ${
                      selectedPayment === method.id
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={`h-6 w-6 ${method.color}`} />
                      <span className="font-medium">{method.name}</span>
                    </div>
                    <span className="text-sm text-gray-600">Select</span>
                  </div>
                );
              })}
            </div>
          </div>

          <Button
            onClick={handleBuyCredits}
            disabled={!selectedPayment || !creditAmount || loading}
            className="w-full"
            size="lg"
          >
            {loading ? 'Processing...' : 'Buy Credits'}
          </Button>
        </CardContent>
      </Card>

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="text-gray-500">No transactions yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4">Date</th>
                    <th className="text-left py-3 px-4">Description</th>
                    <th className="text-left py-3 px-4">Credits</th>
                    <th className="text-left py-3 px-4">Amount</th>
                    <th className="text-left py-3 px-4">Payment Method</th>
                    <th className="text-left py-3 px-4">Status</th>
                    <th className="text-left py-3 px-4">Invoice</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => (
                    <tr key={txn.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-4 text-sm">
                        {new Date(txn.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          {txn.transaction_type === 'credit' ? (
                            <ArrowUpCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <ArrowDownCircle className="h-4 w-4 text-red-600" />
                          )}
                          <span className="text-sm">{txn.description}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`font-semibold ${txn.transaction_type === 'credit' ? 'text-green-600' : 'text-red-600'}`}>
                          {txn.transaction_type === 'credit' ? '+' : '-'}{txn.amount}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        {txn.price_paid ? `$${txn.price_paid}` : '-'}
                      </td>
                      <td className="py-3 px-4 text-sm capitalize">
                        {txn.payment_method || '-'}
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                          {txn.status || 'completed'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {txn.transaction_type === 'credit' && txn.price_paid && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownloadInvoice(txn)}
                            className="text-blue-600 hover:text-blue-700"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
