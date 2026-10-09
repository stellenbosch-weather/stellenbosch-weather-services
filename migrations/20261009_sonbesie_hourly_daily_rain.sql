-- Apply once; historical observations retain NULL rain measurements.
ALTER TABLE `SB_THour`
    ADD COLUMN `Rain_1_Tot` DOUBLE NULL DEFAULT NULL,
    ADD COLUMN `Rain_1_Accumulated` DOUBLE NULL DEFAULT NULL;
ALTER TABLE `SB_TDaily`
    ADD COLUMN `Rain_1_Tot` DOUBLE NULL DEFAULT NULL,
    ADD COLUMN `Rain_1_Accumulated` DOUBLE NULL DEFAULT NULL;
