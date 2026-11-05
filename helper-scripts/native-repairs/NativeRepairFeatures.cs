using System;

namespace AdaptPolicies.NativeRepairs
{
    public static class NativeRepairFeatures
    {
        public static bool Enabled(string feature)
        {
            var value = Environment.GetEnvironmentVariable("ADAPTPOLICIES_NATIVE_REPAIRS");
            if (value == null) return false;
            foreach (var entry in value.Split(',')) if (entry.Trim() == feature) return true;
            return false;
        }
    }
}
