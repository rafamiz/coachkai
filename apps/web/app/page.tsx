import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 bg-gradient-to-b from-brand-50 to-white">
      <div className="max-w-md w-full text-center space-y-8">
        <div className="space-y-2">
          <div className="text-6xl">{'\u{1F966}'}</div>
          <h1 className="text-4xl font-bold text-gray-900">NutriCoach</h1>
          <p className="text-lg text-gray-600">
            Your AI nutrition coach, right in WhatsApp
          </p>
        </div>

        <div className="space-y-3 text-left bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <Feature icon={'\u{1F4F8}'} text="Send a photo of your meal for instant analysis" />
          <Feature icon={'\u{1F4CA}'} text="Track calories, macros, and progress" />
          <Feature icon={'\u{1F3AF}'} text="Personalized advice for your goals" />
          <Feature icon={'\u{1F372}'} text="Get recipes and grocery lists" />
          <Feature icon={'\u{1F4AC}'} text="All through WhatsApp - no app to install" />
        </div>

        <div className="space-y-3">
          <Link
            href="/onboarding/welcome"
            className="block w-full py-4 px-6 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl text-center transition-colors"
          >
            Get Started Free
          </Link>
          <p className="text-sm text-gray-500">7-day free trial. No credit card required.</p>
        </div>
      </div>
    </main>
  );
}

function Feature({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-xl mt-0.5">{icon}</span>
      <span className="text-gray-700">{text}</span>
    </div>
  );
}
