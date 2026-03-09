import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Wallet, ArrowUpCircle, ArrowDownCircle, CreditCard, TrendingUp, Minus, Download } from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const CREDIT_PACKAGES = [
  { credits: 10, price: 100, popular: false },
  { credits: 50, price: 450, popular: true },
  { credits: 100, price: 800, popular: false },
  { credits: 200, price: 1500, popular: false },
];

const PAYMENT_METHODS = [
  { id: 'razorpay', name: 'Razorpay', icon: CreditCard, color: 'text-blue-600' },
];

export default function WalletPage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState(0);
  const [transactions, setTransactions] = useState([]);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [loading, setLoading] = useState(false);

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
  }, [user]);

  const fetchBalance = async () => {
    try {
      const response = await api.get('/wallet/balance');
      setBalance(response.balance || 0);
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

  const handleDownloadInvoice = (txn) => {
    const invoiceContent = `
INVOICE
========================================
Transaction ID: ${txn.id}
Date: ${new Date(txn.created_at).toLocaleDateString()}
Description: ${txn.description}
Credits: ${txn.amount}
Amount Paid: ₹${txn.price_paid || 0}
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

    setLoading(true);
    try {
      // Create order
      const orderResponse = await api.post('/wallet/create-order', {
        credits: 10,
        payment_method: selectedPayment
      });

      // Simulate payment success (in production, integrate with actual payment gateway)
      const paymentResponse = await api.post('/wallet/payment-success', {
        order_id: orderResponse.order_id,
        transaction_id: `TXN_${Date.now()}`,
        credits: 10,
        payment_method: selectedPayment,
        amount_paid: 100
      });

      alert(`Successfully purchased 10 credits!`);
      setSelectedPayment(null);
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

      {/* Wallet Balance Card */}
      <Card className="bg-gradient-to-r from-blue-500 to-blue-600 text-white">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm opacity-90">Wallet Balance</p>
              <h2 className="text-4xl font-bold mt-2">₹{totalCredits * 10}</h2>
              <p className="text-sm mt-2 opacity-90">Available Credits: {remainingCredits}</p>
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


      <Card>
        <CardHeader>
          <CardTitle>Buy Credits</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Payment Methods */}
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

          {/* Buy Button */}
          <Button
            onClick={handleBuyCredits}
            disabled={!selectedPayment || loading}
            className="w-full"
            size="lg"
          >
            {loading ? 'Processing...' : 'Buy Credits'}
          </Button>
        </CardContent>
      </Card>

      {/* Usage Summary */}
      <div className="bg-gray-900 rounded-xl shadow-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-white text-lg font-medium">
            {new Date(new Date().setMonth(new Date().getMonth() - 1)).toLocaleDateString('en-US', { month: 'short', day: '2-digit' })} to {new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit' })} Usage
          </h3>
          <Button variant="outline" className="text-white border-gray-700 hover:bg-gray-800">
            Show Breakdown
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Side - Usage Details */}
          <div className="space-y-4">
            <div className="flex justify-between items-center text-gray-300">
              <span>Current Usage</span>
              <span className="text-white font-semibold">₹{usedCredits * 10}</span>
            </div>
            <div className="flex justify-between items-center text-gray-300">
              <span>Included Usage</span>
              <span className="text-white font-semibold">₹{totalCredits * 10}</span>
            </div>
          </div>

          {/* Right Side - Stat Cards */}
          <div className="space-y-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">Current Usage</p>
              <p className="text-white text-2xl font-bold">₹{usedCredits * 10}</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">Estimated Bill</p>
              <p className="text-white text-2xl font-bold">₹{totalCredits * 10}</p>
            </div>
            <Button className="w-full bg-gray-800 hover:bg-gray-700 text-white border-gray-700">
              Set usage limits
            </Button>
          </div>
        </div>
      </div>

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
                        <span
                          className={`font-semibold ${
                            txn.transaction_type === 'credit'
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {txn.transaction_type === 'credit' ? '+' : '-'}
                          {txn.amount}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        {txn.price_paid ? `₹${txn.price_paid}` : '-'}
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
