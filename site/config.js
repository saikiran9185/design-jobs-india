/* Supabase connection.
 *
 * Both values below are PUBLIC by design — the anon key is safe in a browser
 * because row-level security decides what it may read and write. It can insert a
 * pending submission and read approved listings, and nothing else. Never put the
 * service_role key here; that one lives only in GitHub Actions secrets.
 *
 * Fill these in after running supabase/schema.sql. Until then the site works
 * exactly as before and the submit button explains that it is not set up yet.
 */
window.DJI_CONFIG = {
  SUPABASE_URL: "",       // https://xxxxxxxxxxxx.supabase.co
  SUPABASE_ANON_KEY: "",  // the "anon public" key from Settings > API
};
