'use client';

export default function SuccessPage() {
  const waNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || '+1234567890';
  const waLink = `https://wa.me/${waNumber.replace('+', '')}?text=Hi`;

  return (
    <div className="flex-1 flex flex-col justify-center text-center space-y-8">
      <div className="text-7xl">{'\u{1F389}'}</div>

      <div className="space-y-2">
        <h1 className="text-3xl font-bold">You&apos;re All Set!</h1>
        <p className="text-gray-600">
          Your AI nutrition coach is ready. Send your first meal to get started!
        </p>
      </div>

      <div className="space-y-4">
        <a
          href={waLink}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full py-4 bg-[#25D366] hover:bg-[#20bd5a] text-white font-semibold rounded-xl transition-colors"
        >
          Open WhatsApp
        </a>
        <a
          href="/dashboard"
          className="block w-full py-4 border-2 border-gray-200 text-gray-700 font-semibold rounded-xl hover:bg-gray-50 transition-colors"
        >
          Go to Dashboard
        </a>
      </div>

      <div className="bg-gray-50 rounded-xl p-4 text-left space-y-2">
        <p className="font-medium text-sm">Quick tips:</p>
        <p className="text-sm text-gray-600">{'\u{1F4F8}'} Send a photo of your meal for instant analysis</p>
        <p className="text-sm text-gray-600">{'\u{1F4DD}'} Or just describe it: &quot;chicken salad with avocado&quot;</p>
        <p className="text-sm text-gray-600">{'\u{1F4A7}'} Track water: &quot;drank 500ml water&quot;</p>
        <p className="text-sm text-gray-600">{'\u{2696}\u{FE0F}'} Log weight: &quot;I weigh 72kg&quot;</p>
      </div>
    </div>
  );
}
