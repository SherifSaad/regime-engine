"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ProfilePage() {
  const [displayName, setDisplayName] = useState("");
  const [country, setCountry] = useState("");
  const [ageRange, setAgeRange] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: PATCH /api/user/profile or your auth provider's profile API
    console.log("Profile (not connected):", { displayName, country, ageRange });
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
      <p className="mt-2 text-sm text-zinc-600">
        All fields are optional. You are not required to provide country, age, or any other personal details by law.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        <div className="space-y-2">
          <Label htmlFor="profile-display">Display name <span className="text-zinc-400 font-normal">(optional)</span></Label>
          <Input
            id="profile-display"
            type="text"
            autoComplete="name"
            placeholder="How you’d like to be called"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="profile-country">Country or region <span className="text-zinc-400 font-normal">(optional)</span></Label>
          <select
            id="profile-country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="flex h-9 w-full rounded-md border border-zinc-300 bg-white px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
          >
            <option value="">Prefer not to say</option>
            <option value="CA">Canada</option>
            <option value="US">United States</option>
            <option value="GB">United Kingdom</option>
            <option value="OTHER">Other</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="profile-age">Age range <span className="text-zinc-400 font-normal">(optional)</span></Label>
          <select
            id="profile-age"
            value={ageRange}
            onChange={(e) => setAgeRange(e.target.value)}
            className="flex h-9 w-full rounded-md border border-zinc-300 bg-white px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
          >
            <option value="">Prefer not to say</option>
            <option value="18-24">18–24</option>
            <option value="25-34">25–34</option>
            <option value="35-44">35–44</option>
            <option value="45-54">45–54</option>
            <option value="55-64">55–64</option>
            <option value="65+">65+</option>
          </select>
        </div>

        {saved ? <p className="text-sm text-green-600">Preferences saved.</p> : null}

        <Button type="submit" disabled={saved}>
          Save preferences
        </Button>
      </form>
    </div>
  );
}
