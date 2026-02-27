import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function SignupPage() {
  return (
    <div className="mx-auto max-w-sm">
        <h1 className="text-2xl font-bold tracking-tight">Sign up</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Free. No credit card required.
        </p>
        <div className="mt-8">
          <Button asChild className="w-full">
            <Link href="/app">Continue</Link>
          </Button>
          <p className="mt-4 text-center text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-zinc-900 hover:underline">
              Log in
            </Link>
          </p>
        </div>
    </div>
  )
}
