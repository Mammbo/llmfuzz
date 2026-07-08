# libtiff_rgba — hard branches

8 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `tif_fax3.c:363` | `_TIFFFax3fillruns` | true arm never taken | 25875 |
| 2 | `tif_lzw.c:468` | `tif_lzw.c:LZWDecode` | true arm never taken | 449 |
| 3 | `tif_lzw.c:488` | `tif_lzw.c:LZWDecode` | true arm never taken | 444 |
| 4 | `tif_getimage.c:2704` | `tif_getimage.c:PickContigCase` | true arm never taken | 270 |
| 5 | `tif_getimage.c:2753` | `tif_getimage.c:PickContigCase` | true arm never taken | 129 |
| 6 | `tif_predict.c:128` | `tif_predict.c:PredictorSetupDecode` | true arm never taken | 92 |
| 7 | `tif_jpeg.c:1027` | `tif_jpeg.c:JPEGSetupDecode` | false arm never taken | 52 |
| 8 | `tif_pixarlog.c:612` | `tif_pixarlog.c:PixarLogGuessDataFmt` | true arm never taken | 6 |

## 1. `tif_fax3.c:363`  (true arm never taken)
```c
  357  
  358  	if ((erun-runs)&1)
  359  	    *erun++ = 0;
  360  	x = 0;
  361  	for (; runs < erun; runs += 2) {
  362  	    run = runs[0];
  363  	    if (x+run > lastx || run > lastx )  <-- TARGET (unexplored)
  364  		run = runs[0] = (uint32_t) (lastx - x);
  365  	    if (run) {
  366  		cp = buf + (x>>3);
  367  		bx = x&7;
```

## 2. `tif_lzw.c:468`  (true arm never taken)
```c
  462  		}
  463  		codep = sp->dec_codetab + code;
  464  
  465  		/*
  466  		 * Add the new entry to the code table.
  467  		 */
  468  		if (free_entp < &sp->dec_codetab[0] ||  <-- TARGET (unexplored)
  469  		    free_entp >= &sp->dec_codetab[CSIZE]) {
  470  			TIFFErrorExt(tif->tif_clientdata, module,
  471  			    "Corrupted LZW table at scanline %"PRIu32,
  472  			    tif->tif_row);
```

## 3. `tif_lzw.c:488`  (true arm never taken)
```c
  482  			return (0);
  483  		}
  484  		free_entp->firstchar = free_entp->next->firstchar;
  485  		free_entp->length = free_entp->next->length+1;
  486  		free_entp->value = (codep < free_entp) ?
  487  		    codep->firstchar : free_entp->firstchar;
  488  		if (++free_entp > maxcodep) {  <-- TARGET (unexplored)
  489  			if (++nbits > BITS_MAX)		/* should not happen */
  490  				nbits = BITS_MAX;
  491  			nbitsmask = MAXCODE(nbits);
  492  			maxcodep = sp->dec_codetab + nbitsmask-1;
```

## 4. `tif_getimage.c:2704`  (true arm never taken)
```c
 2698  					case 4:
 2699  						img->put.contig = put4bitcmaptile;
 2700  						break;
 2701  					case 2:
 2702  						img->put.contig = put2bitcmaptile;
 2703  						break;
 2704  					case 1:  <-- TARGET (unexplored)
 2705  						img->put.contig = put1bitcmaptile;
 2706  						break;
 2707  				}
 2708  			}
```

## 5. `tif_getimage.c:2753`  (true arm never taken)
```c
 2747  					 * some OJPEG files
 2748  					 */
 2749  					uint16_t SubsamplingHor;
 2750  					uint16_t SubsamplingVer;
 2751  					TIFFGetFieldDefaulted(img->tif, TIFFTAG_YCBCRSUBSAMPLING, &SubsamplingHor, &SubsamplingVer);
 2752  					switch ((SubsamplingHor<<4)|SubsamplingVer) {
 2753  						case 0x44:  <-- TARGET (unexplored)
 2754  							img->put.contig = putcontig8bitYCbCr44tile;
 2755  							break;
 2756  						case 0x42:
 2757  							img->put.contig = putcontig8bitYCbCr42tile;
```

## 6. `tif_predict.c:128`  (true arm never taken)
```c
  122  		return 0;
  123  
  124  	if (sp->predictor == 2) {
  125  		switch (td->td_bitspersample) {
  126  			case 8:  sp->decodepfunc = horAcc8; break;
  127  			case 16: sp->decodepfunc = horAcc16; break;
  128  			case 32: sp->decodepfunc = horAcc32; break;  <-- TARGET (unexplored)
  129  		}
  130  		/*
  131  		 * Override default decoding method with one that does the
  132  		 * predictor stuff.
```

## 7. `tif_jpeg.c:1027`  (false arm never taken)
```c
 1021  	assert(sp != NULL);
 1022  	assert(sp->cinfo.comm.is_decompressor);
 1023  
 1024  	/* Read JPEGTables if it is present */
 1025  	if (TIFFFieldSet(tif,FIELD_JPEGTABLES)) {
 1026  		TIFFjpeg_tables_src(sp);
 1027  		if(TIFFjpeg_read_header(sp,FALSE) != JPEG_HEADER_TABLES_ONLY) {  <-- TARGET (unexplored)
 1028  			TIFFErrorExt(tif->tif_clientdata, "JPEGSetupDecode", "Bogus JPEGTables field");
 1029  			return (0);
 1030  		}
 1031  	}
```

## 8. `tif_pixarlog.c:612`  (true arm never taken)
```c
  606  	int format = td->td_sampleformat;
  607  
  608  	/* If the user didn't tell us his datafmt,
  609  	 * take our best guess from the bitspersample.
  610  	 */
  611  	switch (td->td_bitspersample) {
  612  	 case 32:  <-- TARGET (unexplored)
  613  		if (format == SAMPLEFORMAT_IEEEFP)
  614  			guess = PIXARLOGDATAFMT_FLOAT;
  615  		break;
  616  	 case 16:
```
