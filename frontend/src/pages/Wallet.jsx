import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
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

const PLAN_OPTIONS = {
  monthly: [
    {
      id: 'starter',
      name: 'Starter',
      price: 66,
      priceLabel: '$66',
      interviewCredits: 10,
      jobPostings: 5,
      userSeats: 4,
      resumeScoring: 500,
      resumeScoringUnlimited: false,
    },
    {
      id: 'growth',
      name: 'Growth',
      price: 45,
      priceLabel: '$45',
      interviewCredits: 30,
      jobPostings: 20,
      userSeats: 11,
      resumeScoring: null,
      resumeScoringUnlimited: true,
    },
    {
      id: 'custom',
      name: 'Custom',
      price: null,
      priceLabel: 'Custom',
      interviewCredits: null,
      jobPostings: null,
      userSeats: null,
      resumeScoring: null,
      resumeScoringUnlimited: true,
    },
  ],
  yearly: [
    {
      id: 'starter',
      name: 'Starter',
      price: 720,
      priceLabel: '$720',
      interviewCredits: 150,
      jobPostings: 5,
      userSeats: 4,
      resumeScoring: 500,
      resumeScoringUnlimited: false,
    },
    {
      id: 'growth',
      name: 'Growth',
      price: 499,
      priceLabel: '$499',
      interviewCredits: 360,
      jobPostings: 20,
      userSeats: 11,
      resumeScoring: null,
      resumeScoringUnlimited: true,
    },
    {
      id: 'custom',
      name: 'Custom',
      price: null,
      priceLabel: 'Custom',
      interviewCredits: null,
      jobPostings: null,
      userSeats: null,
      resumeScoring: null,
      resumeScoringUnlimited: true,
    },
  ],
};

export default function WalletPage({ superAdminAgencyId = null }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const isAdmin = user?.role === 'admin';
  const [balance, setBalance] = useState(0);
  const [transactions, setTransactions] = useState([]);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [creditAmount, setCreditAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [showLowCreditModal, setShowLowCreditModal] = useState(false);
  const [discount, setDiscount] = useState(null);
  const [agencyWalletData, setAgencyWalletData] = useState(null);
  const [historyFilter, setHistoryFilter] = useState('all');
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [selectedPlan, setSelectedPlan] = useState('');
  const [planStatus, setPlanStatus] = useState(null);

  const currentPlanOptions = PLAN_OPTIONS[billingCycle];
  const selectedPlanConfig = currentPlanOptions.find((plan) => plan.id === selectedPlan) || null;

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

  const filteredTransactions = transactions.filter((txn) => {
    if (historyFilter === 'credit') return txn.transaction_type === 'credit';
    if (historyFilter === 'debit') return txn.transaction_type === 'debit';
    return true;
  });

  useEffect(() => {
    if (isSuperAdmin) {
      if (superAdminAgencyId) {
        fetchAgencyWallet(superAdminAgencyId);
      } else {
        setAgencyWalletData(null);
        setTransactions([]);
        setBalance(0);
      }
      return;
    }

    fetchBalance();
    fetchTransactions();
    if (isAdmin) {
      fetchDiscount();
      fetchPlanStatus();
    }
  }, [user, superAdminAgencyId]);

  useEffect(() => {
    if (isSuperAdmin || !isAdmin) return;
    if (searchParams.get('lowCredits') === '1') {
      setShowLowCreditModal(true);
    }
  }, [isAdmin, isSuperAdmin, searchParams]);

  const fetchDiscount = async () => {
    if (!user?.agency_id) return;
    try {
      const res = await api.get(`/pricing/discounts/agency/${user.agency_id}`);
      setDiscount(res || null);
    } catch {
      setDiscount(null);
    }
  };

  const fetchAgencyWallet = async (agencyId) => {
    try {
      const response = await api.get(`/wallet/agency-admin/${agencyId}`);
      setAgencyWalletData(response);
      setBalance(response?.admin?.wallet_balance || 0);
      setTransactions(Array.isArray(response?.transactions) ? response.transactions : []);
    } catch (error) {
      console.error('Failed to fetch agency wallet:', error);
      setAgencyWalletData(null);
      setBalance(0);
      setTransactions([]);
    }
  };

  const getDiscountedAmount = (amount) => {
    if (!discount || !amount || isNaN(amount)) return null;
    const original = parseFloat(amount);
    if (discount.discount_type === 'percentage') {
      const discountAmt = (original * discount.discount_value) / 100;
      return { original, discountAmt, final: original - discountAmt, label: `${discount.discount_value}% off` };
    } else {
      const discountAmt = Math.min(discount.discount_value, original);
      const sym = discount.currency === 'INR' ? '₹' : '$';
      return { original, discountAmt, final: original - discountAmt, label: `${sym}${discount.discount_value} off` };
    }
  };

  const fetchBalance = async () => {
    try {
      const response = await api.get('/wallet/balance');
      const bal = response.balance || 0;
      setBalance(bal);
      if (isAdmin && bal <= 10) {
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

  const fetchPlanStatus = async () => {
    if (!isAdmin) {
      setPlanStatus(null);
      return;
    }

    try {
      const usageSnapshot = await getPlanUsageSnapshot();
      const subscription = usageSnapshot.subscription;

      if (!subscription) {
        setPlanStatus(null);
        return;
      }

      const interviewTotal = subscription.interview_credits_total || 0;
      const interviewUsed = usageSnapshot.interviewCreditsUsed || 0;
      const resumeTotal = subscription.resume_scoring_limit;
      const resumeUsed = usageSnapshot.resumeScoringUsed || 0;
      const jobsTotal = subscription.is_unlimited_jobs ? null : subscription.max_job_posts;
      const jobsUsed = usageSnapshot.activeJobCount || 0;
      const seatsTotal = subscription.max_users;
      const seatsUsed = usageSnapshot.activeUserCount || 0;

      setPlanStatus({
        planName: subscription.plan_name,
        billingType: subscription.billing_type,
        interviewsRemaining: Math.max(interviewTotal - interviewUsed, 0),
        interviewsTotal: interviewTotal,
        resumeRemaining: subscription.is_unlimited_resume_scoring ? null : Math.max((resumeTotal || 0) - resumeUsed, 0),
        resumeTotal,
        resumeUnlimited: subscription.is_unlimited_resume_scoring,
        jobsRemaining: subscription.is_unlimited_jobs ? null : Math.max((jobsTotal || 0) - jobsUsed, 0),
        jobsTotal,
        jobsUnlimited: subscription.is_unlimited_jobs,
        seatsRemaining: seatsTotal == null ? null : Math.max(seatsTotal - seatsUsed, 0),
        seatsTotal,
      });
    } catch (error) {
      console.error('Failed to fetch plan status:', error);
      setPlanStatus(null);
    }
  };

  const getTransactionUsageLabel = (txn) => {
    const description = (txn.description || '').toLowerCase();

    if (txn.transaction_type === 'debit') {
      if (description.includes('interview completed')) {
        return 'Interview done';
      }
      return 'Credits used';
    }

    if (description.includes('purchased')) {
      return 'Credits purchased';
    }

    if (description.includes('trial')) {
      return 'Trial credits';
    }

    if (description.includes('super admin')) {
      return 'Added by super admin';
    }

    return 'Credits added';
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

    setLoading(true);
    try {
      if (selectedPlanConfig && selectedPlanConfig.id !== 'custom' && isAdmin) {
        const usageSnapshot = await getPlanUsageSnapshot();
        const validationErrors = validatePresetPlanSelection(selectedPlanConfig, usageSnapshot);

        if (validationErrors.length > 0) {
          alert(`This ${billingCycle} plan cannot be selected right now:\n\n${validationErrors.join('\n')}`);
          return;
        }

        const includedCredits = selectedPlanConfig.interviewCredits;
        const userCount = Math.max(usageSnapshot.activeUserCount || 1, 1);
        const orderResponse = await api.post('/wallet/create-order', {
          credits: includedCredits,
          payment_method: selectedPayment
        });

        await api.post('/wallet/payment-success', {
          order_id: orderResponse.order_id,
          transaction_id: `TXN_${Date.now()}`,
          credits: includedCredits,
          payment_method: selectedPayment,
          amount_paid: selectedPlanConfig.price
        });

        await api.post('/subscriptions/select-plan', {
          user_id: user.id,
          plan_name: selectedPlanConfig.id,
          billing_type: billingCycle,
          user_count: userCount
        });

        alert(`Successfully activated the ${selectedPlanConfig.name} ${billingCycle} plan with ${includedCredits} interview credits!`);
        setSelectedPayment(null);
        setSelectedPlan('');
        setCreditAmount('');
        fetchBalance();
        fetchTransactions();
        fetchPlanStatus();
        return;
      }

      const credits = parseInt(creditAmount);
      const price = parseInt(creditAmount);
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
      setSelectedPlan('');
      setCreditAmount('');
      fetchBalance();
      fetchTransactions();
      fetchPlanStatus();
    } catch (error) {
      alert('Payment failed: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBillingCycleChange = (value) => {
    setBillingCycle(value);
    setSelectedPlan('');
    setCreditAmount('');
  };

  const handlePlanChange = (value) => {
    setSelectedPlan(value);
    const plan = currentPlanOptions.find((option) => option.id === value);
    setCreditAmount(plan?.id === 'custom' ? '' : String(plan?.price || ''));
  };

  const getPlanUsageSnapshot = async () => {
    const [subscription, activeUsers, jobsCount] = await Promise.all([
      isAdmin ? api.get('/subscriptions/current').catch(() => null) : Promise.resolve(null),
      user?.agency_id ? api.getUsersByAgency(user.agency_id).catch(() => []) : Promise.resolve([]),
      api.getJobsCount({ is_active: true }).catch(() => ({ count: 0 })),
    ]);

    return {
      subscription,
      activeUserCount: Array.isArray(activeUsers) && activeUsers.length > 0
        ? activeUsers.length
        : Math.max(subscription?.current_users || 0, user ? 1 : 0),
      activeJobCount: subscription?.used_job_posts ?? jobsCount?.count ?? 0,
      interviewCreditsUsed: subscription?.interview_credits_used || 0,
      resumeScoringUsed: subscription?.resume_scoring_used || 0,
    };
  };

  const validatePresetPlanSelection = (planConfig, usageSnapshot) => {
    const errors = [];

    if ((usageSnapshot.interviewCreditsUsed || 0) > planConfig.interviewCredits) {
      errors.push(`Interview credits used (${usageSnapshot.interviewCreditsUsed}) exceed the ${planConfig.name} ${billingCycle} limit of ${planConfig.interviewCredits}.`);
    }

    if ((usageSnapshot.activeJobCount || 0) > planConfig.jobPostings) {
      errors.push(`Active job postings (${usageSnapshot.activeJobCount}) exceed the ${planConfig.name} ${billingCycle} limit of ${planConfig.jobPostings}.`);
    }

    if ((usageSnapshot.activeUserCount || 0) > planConfig.userSeats) {
      errors.push(`Active user seats (${usageSnapshot.activeUserCount}) exceed the ${planConfig.name} ${billingCycle} limit of ${planConfig.userSeats}.`);
    }

    if (
      !planConfig.resumeScoringUnlimited &&
      (usageSnapshot.resumeScoringUsed || 0) > (planConfig.resumeScoring || 0)
    ) {
      errors.push(`Resume scans used (${usageSnapshot.resumeScoringUsed}) exceed the ${planConfig.name} ${billingCycle} limit of ${planConfig.resumeScoring}.`);
    }

    return errors;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Wallet</h1>
          {isSuperAdmin && (
            <p className="mt-1 text-sm text-muted-foreground">
              {superAdminAgencyId && agencyWalletData?.agency
                ? `Managing ${agencyWalletData.agency.name} admin wallet`
                : 'Select an agency from the filter to manage its admin wallet'}
            </p>
          )}
        </div>
      </div>

      {/* Low Credit Modal */}
      {!isSuperAdmin && showLowCreditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-yellow-100 p-2 rounded-full">
                <Wallet className="h-6 w-6 text-yellow-600" />
              </div>
              <h2 className="text-lg font-bold text-gray-900">Low Credits Warning</h2>
            </div>
            <p className="text-gray-600 text-sm mb-4">
              Your credits are low. To continue the service do recharge.
            </p>
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setShowLowCreditModal(false);
                  searchParams.delete('lowCredits');
                  setSearchParams(searchParams);
                }}
              >
                Cancel
              </Button>
              <Button
                className="flex-1"
                onClick={() => {
                  setShowLowCreditModal(false);
                  searchParams.delete('lowCredits');
                  setSearchParams(searchParams);
                  document.getElementById('creditAmount')?.focus();
                }}
              >
                Proceed to Payment
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Wallet Balance Card */}
      <Card className="bg-gradient-to-r from-blue-500 to-blue-600 text-white">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm opacity-90">{isSuperAdmin ? 'Agency Admin Wallet Balance' : 'Wallet Balance'}</p>
              <h2 className="text-4xl font-bold mt-2">{remainingCredits} Credits</h2>
            </div>
            <Wallet className="h-16 w-16 opacity-20" />
          </div>
        </CardContent>
      </Card>

      {!isSuperAdmin && isAdmin && planStatus && (
        <Card>
          <CardHeader>
            <CardTitle>
              Plan Usage Status
              <span className="ml-2 text-sm font-normal text-muted-foreground capitalize">
                {planStatus.planName} ({planStatus.billingType})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Interviews Remaining</p>
                <p className="mt-2 text-2xl font-bold">{planStatus.interviewsRemaining}</p>
                <p className="mt-1 text-xs text-muted-foreground">of {planStatus.interviewsTotal}</p>
              </div>

              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Resume Scans Remaining</p>
                <p className="mt-2 text-2xl font-bold">
                  {planStatus.resumeUnlimited ? 'Unlimited' : planStatus.resumeRemaining}
                </p>
                {!planStatus.resumeUnlimited && (
                  <p className="mt-1 text-xs text-muted-foreground">of {planStatus.resumeTotal}</p>
                )}
              </div>

              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Jobs Remaining</p>
                <p className="mt-2 text-2xl font-bold">
                  {planStatus.jobsUnlimited ? 'Unlimited' : planStatus.jobsRemaining}
                </p>
                {!planStatus.jobsUnlimited && (
                  <p className="mt-1 text-xs text-muted-foreground">of {planStatus.jobsTotal}</p>
                )}
              </div>

              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Seats Remaining</p>
                <p className="mt-2 text-2xl font-bold">
                  {planStatus.seatsRemaining == null ? 'Custom' : planStatus.seatsRemaining}
                </p>
                {planStatus.seatsRemaining != null && (
                  <p className="mt-1 text-xs text-muted-foreground">of {planStatus.seatsTotal}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

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

      {/* Buy Credits */}
      {!isSuperAdmin && (
      <Card>
        <CardHeader>
          <CardTitle>Buy Credits</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="billingCycle">Billing Cycle</Label>
            <select
              id="billingCycle"
              value={billingCycle}
              onChange={(e) => handleBillingCycleChange(e.target.value)}
              className="mt-2 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="Empty"></option>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>

          <div>
            <Label htmlFor="creditAmount">Choose Plan</Label>
            <select
              id="creditAmount"
              value={selectedPlan}
              onChange={(e) => handlePlanChange(e.target.value)}
              className="mt-2 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Select a plan</option>
              {currentPlanOptions.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name} - {plan.priceLabel}
                </option>
              ))}
            </select>

            {selectedPlan === 'custom' && (
              <Input
                id="customCreditAmount"
                type="number"
                placeholder="Enter custom amount"
                value={creditAmount}
                onChange={(e) => setCreditAmount(e.target.value)}
                min="1"
                className="mt-3"
              />
            )}

            {selectedPlanConfig && selectedPlanConfig.id !== 'custom' && (
              <div className="mt-3 rounded-lg border bg-slate-50 p-4 space-y-1 text-sm text-slate-700">
                <p className="font-medium text-slate-900">
                  {selectedPlanConfig.name} includes {selectedPlanConfig.interviewCredits} interview credits for {selectedPlanConfig.priceLabel}/{billingCycle === 'monthly' ? 'month' : 'year'}
                </p>
                <p>Resume scans: {selectedPlanConfig.resumeScoringUnlimited ? 'Unlimited' : selectedPlanConfig.resumeScoring}</p>
                <p>Active job postings: {selectedPlanConfig.jobPostings}{billingCycle === 'monthly' ? '' : '/month'}</p>
                <p>User seats: {selectedPlanConfig.userSeats}</p>
              </div>
            )}

            {creditAmount && (!selectedPlanConfig || selectedPlanConfig.id === 'custom') && (
              <p className="text-sm text-gray-500 mt-2">
                You will get {creditAmount} credits ($1 per credit)
              </p>
            )}

            {/* Discount Breakdown */}
            {(() => {
              const calc = getDiscountedAmount(creditAmount);
              if (!calc) return null;
              const sym = discount?.currency === 'INR' ? '₹' : '$';
              return (
                <div className="mt-3 border rounded-lg p-4 bg-green-50 dark:bg-green-900/20 space-y-2">
                  <p className="text-xs font-semibold text-green-700 dark:text-green-400 mb-1">
                    🎉 You have a special discount of {calc.label} on credit purchases
                  </p>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Original Amount</span>
                    <span>{sym}{calc.original.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm text-green-600 dark:text-green-400">
                    <span>Discount ({calc.label})</span>
                    <span>- {sym}{calc.discountAmt.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm font-bold border-t pt-2">
                    <span>Amount to Pay</span>
                    <span>{sym}{calc.final.toFixed(2)}</span>
                  </div>
                </div>
              );
            })()}
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
      )}

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>{isSuperAdmin ? 'Agency Admin Transaction History' : 'Credits History'}</CardTitle>
            <select
              className="h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
              value={historyFilter}
              onChange={(e) => setHistoryFilter(e.target.value)}
            >
              <option value="all">All</option>
              <option value="credit">Credit</option>
              <option value="debit">Debit / Deduct</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {isSuperAdmin && !superAdminAgencyId ? (
            <p className="text-gray-500">Select an agency from the filter to view its admin wallet transactions.</p>
          ) : filteredTransactions.length === 0 ? (
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
                    <th className="text-left py-3 px-4">Usage</th>
                    <th className="text-left py-3 px-4">Invoice</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransactions.map((txn) => (
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
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2 py-1 rounded ${
                          txn.transaction_type === 'debit'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {getTransactionUsageLabel(txn)}
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
