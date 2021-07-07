parted -a optimal /dev/sdc
mklabel gpt
mkpart primary 1 -1
align-check
optimal
1
quit


cryptsetup luksFormat -c aes-xts-plain64 -s 512 -h sha512 /dev/sda1

cryptsetup luksOpen /dev/sda1 cachedrive2

mkfs.ext4 /dev/mapper/cachedrive2


cryptsetup luksAddKey /dev/sda1 /media/usbstick1/k_file_c2

/media/paritydrive1/.snapraid /media/paritydrive2/.snapraid

blkid | grep crypto_LUKS

sudo vi /etc/crypttab

cachedrive2 UUID=XXX /media/usbstick1/k_file_c2 luks

sudo update-initramfs -u


blkid | grep mapper


sudo vi /etc/fstab
UUID=XXX /media/cachedrive2	ext4 	defaults 0 2




sudo vi /etc/fstab

/media/cachedrive* /media/cache fuse.mergerfs allow_other,direct_io,use_ino,category.create=lfs,moveonenospc=true,minfreespace=20G,fsname=mergerfsPool 0 0