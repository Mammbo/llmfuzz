# libtiff_cp — hard branches

9 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `tiffcp.c:1973` | `tiffcp.c:pickCopyFunc` | true arm never taken | 3344 |
| 2 | `tiffcp.c:746` | `tiffcp.c:tiffcp` | true arm never taken | 3326 |
| 3 | `tiffcp.c:1415` | `tiffcp.c:cpImage` | false arm never taken | 356 |
| 4 | `tif_dirread.c:5303` | `tif_dirread.c:TIFFFetchNormalTag` | true arm never taken | 59627 |
| 5 | `tif_dirread.c:5418` | `tif_dirread.c:TIFFFetchNormalTag` | true arm never taken | 59627 |
| 6 | `tif_dirread.c:889` | `tif_dirread.c:TIFFReadDirEntryArrayWithLimit` | false arm never taken | 8967 |
| 7 | `tif_dirread.c:843` | `tif_dirread.c:TIFFReadDirEntryArrayWithLimit` | true arm never taken | 17196 |
| 8 | `tif_pixarlog.c:617` | `tif_pixarlog.c:PixarLogGuessDataFmt` | true arm never taken | 5 |
| 9 | `tif_jpeg.c:1036` | `tif_jpeg.c:JPEGSetupDecode` | true arm never taken | 8 |

## 1. `tiffcp.c:1973`  (true arm never taken)
```c
 1967  {
 1968  	uint16_t shortv;
 1969  	uint32_t w, l, tw, tl;
 1970  	int bychunk;
 1971  
 1972  	(void) TIFFGetFieldDefaulted(in, TIFFTAG_PLANARCONFIG, &shortv);
 1973  	if (shortv != config && bitspersample != 8 && samplesperpixel > 1) {  <-- TARGET (unexplored)
 1974  		fprintf(stderr,
 1975  		    "%s: Cannot handle different planar configuration w/ bits/sample != 8\n",
 1976  		    TIFFFileName(in));
 1977  		return (NULL);
```

## 2. `tiffcp.c:746`  (true arm never taken)
```c
  740  	}
  741  	else if (compression == COMPRESSION_SGILOG
  742  	    || compression == COMPRESSION_SGILOG24)
  743  		TIFFSetField(out, TIFFTAG_PHOTOMETRIC,
  744  		    samplesperpixel == 1 ?
  745  		    PHOTOMETRIC_LOGL : PHOTOMETRIC_LOGLUV);
  746  	else if (input_compression == COMPRESSION_JPEG &&  <-- TARGET (unexplored)
  747  			 samplesperpixel == 3 ) {
  748  		/* RGB conversion was forced above
  749  		hence the output will be of the same type */
  750  		TIFFSetField(out, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
```

## 3. `tiffcp.c:1415`  (false arm never taken)
```c
 1409  	tsize_t bytes = scanlinesize * (tsize_t)imagelength;
 1410  	/*
 1411  	 * XXX: Check for integer overflow.
 1412  	 */
 1413  	if (scanlinesize
 1414  	    && imagelength
 1415  	    && bytes / (tsize_t)imagelength == scanlinesize) {  <-- TARGET (unexplored)
 1416  		buf = limitMalloc(bytes);
 1417  		if (buf) {
 1418  			if ((*fin)(in, (uint8_t*)buf, imagelength,
 1419                         imagewidth, spp)) {
```

## 4. `tif_dirread.c:5303`  (true arm never taken)
```c
 5297  							return(0);
 5298  					}
 5299  				}
 5300  			}
 5301  			break;
 5302  		/*--: Rational2Double: Extend for Double Arrays and Rational-Arrays read into Double-Arrays. */
 5303  		case TIFF_SETGET_C0_DOUBLE:  <-- TARGET (unexplored)
 5304  			{
 5305  				double* data;
 5306  				assert(fip->field_readcount>=1);
 5307  				assert(fip->field_passcount==0);
```

## 5. `tif_dirread.c:5418`  (true arm never taken)
```c
 5412  						if (!m)
 5413  							return(0);
 5414  					}
 5415  				}
 5416  			}
 5417  			break;
 5418  		case TIFF_SETGET_C16_UINT64:  <-- TARGET (unexplored)
 5419  			{
 5420  				uint64_t* data;
 5421  				assert(fip->field_readcount==TIFF_VARIABLE);
 5422  				assert(fip->field_passcount==1);
```

## 6. `tif_dirread.c:889`  (false arm never taken)
```c
  883  			return(TIFFReadDirEntryErrAlloc);
  884  	}
  885  	if (!(tif->tif_flags&TIFF_BIGTIFF))
  886  	{
  887  		/* Only the condition on original_datasize_clamped. The second
  888  		 * one is implied, but Coverity Scan cannot see it. */
  889  		if (original_datasize_clamped<=4 && datasize <= 4 )  <-- TARGET (unexplored)
  890  			_TIFFmemcpy(data,&direntry->tdir_offset,datasize);
  891  		else
  892  		{
  893  			enum TIFFReadDirEntryErr err;
```

## 7. `tif_dirread.c:843`  (true arm never taken)
```c
  837          int original_datasize_clamped;
  838  	typesize=TIFFDataWidth(direntry->tdir_type);
  839  
  840          target_count64 = (direntry->tdir_count > maxcount) ?
  841                  maxcount : direntry->tdir_count;
  842  
  843  	if ((target_count64==0)||(typesize==0))  <-- TARGET (unexplored)
  844  	{
  845  		*value=0;
  846  		return(TIFFReadDirEntryErrOk);
  847  	}
```

## 8. `tif_pixarlog.c:617`  (true arm never taken)
```c
  611  	switch (td->td_bitspersample) {
  612  	 case 32:
  613  		if (format == SAMPLEFORMAT_IEEEFP)
  614  			guess = PIXARLOGDATAFMT_FLOAT;
  615  		break;
  616  	 case 16:
  617  		if (format == SAMPLEFORMAT_VOID || format == SAMPLEFORMAT_UINT)  <-- TARGET (unexplored)
  618  			guess = PIXARLOGDATAFMT_16BIT;
  619  		break;
  620  	 case 12:
  621  		if (format == SAMPLEFORMAT_VOID || format == SAMPLEFORMAT_INT)
```

## 9. `tif_jpeg.c:1036`  (true arm never taken)
```c
 1030  		}
 1031  	}
 1032  
 1033  	/* Grab parameters that are same for all strips/tiles */
 1034  	sp->photometric = td->td_photometric;
 1035  	switch (sp->photometric) {
 1036  	case PHOTOMETRIC_YCBCR:  <-- TARGET (unexplored)
 1037  		sp->h_sampling = td->td_ycbcrsubsampling[0];
 1038  		sp->v_sampling = td->td_ycbcrsubsampling[1];
 1039  		break;
 1040  	default:
```
