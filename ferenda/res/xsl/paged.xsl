<?xml version="1.0" encoding="utf-8"?>
<!--
Note: this template expects XHTML1.1, outputs HTML5

It's a generic template for paged content (assumes a bunch of <div class="pdfpage">)
-->
<xsl:stylesheet version="1.0"
		xmlns:xhtml="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dcterms="http://purl.org/dc/terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		exclude-result-prefixes="xhtml rdf dcterms rinfo rinfoex">

  <xsl:include href="base.xsl"/>

  <xsl:template name="headtitle"><xsl:choose><xsl:when test="xhtml:title"><xsl:value-of select="xhtml:title"/></xsl:when><xsl:otherwise>(Title missing)</xsl:otherwise></xsl:choose></xsl:template>
  <xsl:template name="metarobots"><xsl:comment>Robot metatag goes here</xsl:comment></xsl:template>
  <xsl:template name="linkalternate"><xsl:comment>Alternate link(s)</xsl:comment></xsl:template>
  <xsl:template name="headmetadata"><xsl:comment>headmetadata?</xsl:comment></xsl:template>
  <xsl:template name="bodyclass">generic</xsl:template>
  <xsl:template name="pagetitle">
    <h1><xsl:value-of select="../xhtml:head/xhtml:title"/></h1>
  </xsl:template>
  <xsl:param name="dyntoc" select="true()"/>
  <xsl:param name="fixedtoc" select="true()"/>
  <xsl:param name="content-under-pagetitle" select="false()"/>

  <xsl:template match="xhtml:div[@class='pdfpage']">
    <div class="page">
      <!-- Nav tabs -->
      <ul class="nav nav-tabs">
	<li class="active"><a href="#{@id}-text" class="view-text"><xsl:value-of select="@id"/></a></li>
	<li><a href="#{@id}-img" class="view-img"><span class="glyphicon glyphicon-picture">&#160;</span>Original</a></li>
      </ul>
      <div class="pdfpage" id="{@id}" style="{@style}">
	<a href="{@src}" class="facsimile"><img data-src="{@src}"/></a>
	<xsl:apply-templates/>
      </div>
      <!--
      <div class="annotations">
	<p>Annotated content for <xsl:value-of select="@id"/> goes here</p>
	</div>
      -->
    </div>
  </xsl:template>
    
  <!-- default rule: Identity transform -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- toc handling, just list all available pages for now -->
  <xsl:template match="xhtml:div[@class='pdfpage']" mode="toc">
    <li><a href="#{@id}"><xsl:value-of select="@id"/></a></li>
  </xsl:template>

  <!-- toc handling (do nothing) -->
  <xsl:template match="@*|node()" mode="toc"/>
  
</xsl:stylesheet>

