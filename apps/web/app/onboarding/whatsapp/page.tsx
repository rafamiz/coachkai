'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function WhatsAppPage() {
  const router = useRouter();
  const [phone, setPhone] = useState('');
  const [countryCode, setCountryCode] = useState('+1');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'phone' | 'verify' | 'verified'>('phone');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fullPhone = countryCode + phone.replace(/\D/g, '');

  const sendOTP = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/verify-phone/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: fullPhone }),
      });
      if (res.ok) {
        setStep('verify');
      } else {
        setError('Failed to send code. Check your number.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    }
    setLoading(false);
  };

  const verifyOTP = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/verify-phone/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: fullPhone, code }),
      });
      if (res.ok) {
        localStorage.setItem('onboarding_phone', fullPhone);
        setStep('verified');
      } else {
        setError('Invalid code. Try again.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    }
    setLoading(false);
  };

  const handleContinue = () => {
    router.push('/onboarding/subscribe');
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Connect WhatsApp</h1>
        <p className="text-gray-500 mt-1">
          {step === 'verified'
            ? "You're connected!"
            : "You'll chat with NutriCoach directly in WhatsApp"}
        </p>
      </div>

      <div className="flex-1 space-y-4">
        {step === 'phone' && (
          <>
            <div className="flex gap-2">
              <select
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                className="px-3 py-3 rounded-xl border border-gray-300 bg-white text-sm"
              >
                <option value="+1">US +1</option>
                <option value="+44">UK +44</option>
                <option value="+49">DE +49</option>
                <option value="+33">FR +33</option>
                <option value="+34">ES +34</option>
                <option value="+39">IT +39</option>
                <option value="+31">NL +31</option>
                <option value="+61">AU +61</option>
                <option value="+91">IN +91</option>
                <option value="+52">MX +52</option>
                <option value="+55">BR +55</option>
                <option value="+54">AR +54</option>
              </select>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="flex-1 px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
                placeholder="Phone number"
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button
              onClick={sendOTP}
              disabled={!phone || loading}
              className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-200 text-white font-semibold rounded-xl transition-colors"
            >
              {loading ? 'Sending...' : 'Send Verification Code'}
            </button>
          </>
        )}

        {step === 'verify' && (
          <>
            <p className="text-sm text-gray-600">Enter the 6-digit code sent to {fullPhone}</p>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="w-full px-4 py-4 rounded-xl border border-gray-300 text-center text-2xl tracking-[0.5em] focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
              placeholder="000000"
              maxLength={6}
            />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button
              onClick={verifyOTP}
              disabled={code.length !== 6 || loading}
              className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-200 text-white font-semibold rounded-xl transition-colors"
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            <button onClick={() => setStep('phone')} className="w-full text-sm text-gray-500 underline">
              Use a different number
            </button>
          </>
        )}

        {step === 'verified' && (
          <div className="text-center space-y-4 py-8">
            <div className="text-6xl">{'\u{2705}'}</div>
            <p className="text-lg font-medium">WhatsApp connected!</p>
            <p className="text-gray-500 text-sm">
              After setup, just send a photo of your meal or describe it to start tracking.
            </p>
          </div>
        )}
      </div>

      {step === 'verified' && (
        <button
          onClick={handleContinue}
          className="w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
        >
          Continue
        </button>
      )}
    </div>
  );
}
