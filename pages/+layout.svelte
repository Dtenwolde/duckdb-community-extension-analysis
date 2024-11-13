<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout {data} hideSidebar={true} githubRepo='https://github.com/Dtenwolde/duckdb-community-extension-analysis' neverShowQueries={true}>
	<slot slot="content" />
</EvidenceDefaultLayout>