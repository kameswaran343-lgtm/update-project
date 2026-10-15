import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle } from 'lucide-react';

export default function NotFound({ language = 'ta' }: { language?: 'ta' | 'en' }) {
  const title = language === 'ta' ? 'பக்கம் கிடைக்கவில்லை' : '404 Page Not Found';
  const description = language === 'ta' ? 'இந்தப் பக்கத்தைத் திறக்க முடியவில்லை.' : 'This page could not be found.';
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md mx-4">
        <CardContent className="pt-6">
          <div className="flex mb-4 gap-2">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <h1 className="text-2xl font-bold text-gray-900">
              {title}
            </h1>
          </div>

          <p className="mt-4 text-sm text-gray-600">
            {description}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
