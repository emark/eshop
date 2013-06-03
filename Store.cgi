#!/usr/bin/perl -w

use strict;
use lib "/home/hosting_locumtest/usr/local/lib/perl5";
use Mojolicious::Lite;
use Mojo::UserAgent;
use DBIx::Custom;
use Validator::Custom;
use utf8;
use v5.10.0;

open (DBCONF,"< app.conf") || die "Error open dbconfig file";
my @appconf=<DBCONF>;
close DBCONF;
chomp @appconf;

my $storename = $appconf[0];
my $secret = $appconf[4];
my $discounts = {0 => 0, 7000 => 3, 12001 => 5, 17001 => 7};

our $dbi = DBIx::Custom->connect(
			dsn => $appconf[1],
			user => $appconf[2],
			password => $appconf[3],
			option => {mysql_enable_utf8 => 1}
);

$dbi->do('SET NAMES utf8');

our $order = DBIx::Custom::Order->new;

get '/search/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'search'
	};

    $self->stash(
		page => $page,
    );
};

get '/cart/checkout/' => sub{
	my $self = shift;
	return $self->redirect_to('cart') unless $self->session('cartid');
	my $page = {
		url => 'checkout',
	};
	$self->stash(
		page => $page
	);
	$self->render('cart/checkout');
};

post '/cart/checkout/' => sub {
	my $self = shift;
	my $cartid = $self->session('cartid');
	my $orderinfo = $self->req->params->to_hash;
    my $page = {
		'url' => 'checkout',
	};
	$self->stash(
		page => $page,
	);

	my $vc = Validator::Custom->new;
	my $rule = [
		tel => ['not_blank'],
		delivery => ['defined'],
		payment => ['defined'],
	];
	my $vresult = $vc->validate($orderinfo, $rule);
	if($vresult->is_ok && $cartid){
		$orderinfo->{cartid} = $cartid;
		$orderinfo->{sysdate} = \"NOW()";
		$orderinfo->{status} = 0;
		$orderinfo->{storename} = $storename;

		$dbi->insert(
			$orderinfo,
			table => 'orders',
		);
		
		my $result = $dbi->select(
			table => 'products',
		);
		my $products = {};

		while (my $hash = $result->fetch_hash){
			$products->{$hash->{id}} = $hash;
		};

		my $cartitems = {};
		my $discount_base = 0;
		my $total_cart = 0;

		$result = $dbi->select(
            table => 'cart',
            where => {'cartid' => $cartid},
        );

        while(my $hash = $result->fetch_hash){
            $cartitems = $hash;
            $cartitems->{title} = $products->{$hash->{productid}}->{title};
            $cartitems->{price} = $products->{$hash->{productid}}->{price};
			$cartitems->{discount} = $products->{$hash->{productid}}->{discount};
            $cartitems->{id} = '';

			$dbi->insert(
				$cartitems,
				table => 'items',
			);
			
			$discount_base = $discount_base + $cartitems->{price}*$cartitems->{count} if ($cartitems->{discount} == 0);
			$total_cart = $total_cart + $cartitems->{price}*$cartitems->{count};
        };

		if(!$orderinfo->{discount}){
			my $discount = {};
			$discount->{discount} = 0;
			foreach my $key (keys %{$discounts}){
				if ($total_cart > $key && $discount->{discount} < $discounts->{$key}){
					$discount->{discount} = $discounts->{$key};
				};
			};

			$discount->{name} = "$storename-$cartid-$discount->{discount}";

			if($discount->{discount} > 0){

				$dbi->insert(
					$discount,
					table => 'discounts',	
				);
			
				$dbi->update(
					{discount => $discount->{name}},
					table => 'orders',
					where => {cartid => $cartid}
				);
			};
		};

		$self->session('cartid' => 0);
		$self->flash('cartid' => $cartid);

		return $self->redirect_to('/cart/thankyou/');
	}else{
		$self->stash(missing => 1);
	};
	$self->render('cart/checkout');
};

get '/cart/thankyou/' => sub{
	my $self = shift;
	my $page = {
		url => 'thankyou',
	};
	$self->stash(page => $page);
	$self->render('cart/thankyou');
};

get '/cart/payment/:cartid' => sub{
	my $self = shift;
	my $cartid = $self->param('cartid') || 0;
	my $page = {
		url => 'payment',
	};
	my $result = $dbi->select(
		table => 'orders',
		column => [
			'id',
			'cartid',
			'payment',
			'delivery',
			'status',
		],
		where => {cartid => $cartid},
	);
	my $orderinfo = $result->one || undef;
	
	$result = $dbi->select(
		table => 'items',
		column => ['price','count'],
		where => {cartid => $cartid},
	);
	my $itemprice = $result->fetch_all;
	$self->stash(
		page => $page,
		orderinfo => $orderinfo,
		itemprice => $itemprice,
	);
	$self->render('cart/payment');
};

get '/cart/:action/:id' => {action => 'view', id => 0} => sub{
    my $self = shift;
    my $cartid = $self->session('cartid') || 0;
    my $productid = $self->stash('id');
	my $action = $self->stash('action');
	my $result = $dbi->select(
		table => 'products',
	);
	my $products = {};
	while(my $hash = $result->fetch_hash){
		$products->{$hash->{id}} = $hash;
	};
	my $cartitems = {};
	my $page = {
        'url' => 'cart',
    };
	$self->stash(page => $page);

	if($cartid){
		$result = $dbi->select(
			table => 'cart',
			where => {'cartid' => $cartid},
		);
		while(my $hash = $result->fetch_hash){
			$cartitems->{$hash->{productid}} = $hash;
			$cartitems->{$hash->{productid}}->{url} = $products->{$hash->{productid}}->{url};
			$cartitems->{$hash->{productid}}->{caturl} = $products->{$hash->{productid}}->{caturl};
			$cartitems->{$hash->{productid}}->{title} = $products->{$hash->{productid}}->{title};
			$cartitems->{$hash->{productid}}->{price} = $products->{$hash->{productid}}->{price};
			$cartitems->{$hash->{productid}}->{image} = $products->{$hash->{productid}}->{image};
			$cartitems->{$hash->{productid}}->{discount} = $products->{$hash->{productid}}->{discount};
		};
	}else{
		return $self->render('cart/emptycart');
	};

	for ($action){
		if(/delete/){
			$dbi->delete(
				table => 'cart',
				where => {cartid => $cartid, productid => $productid},
			);
			delete $cartitems->{$productid};
		}elsif(/more/){
			$cartitems->{$productid}->{count}++;
			$dbi->update(
				{
					count => $cartitems->{$productid}->{count},
				},
				table => 'cart',
				where => {cartid => $cartid, productid => $productid},
			);
		}elsif(/less/){
			if($cartitems->{$productid}->{count} > 1){
	            $cartitems->{$productid}->{count}--;
    	        $dbi->update(
        	        {
            	        count => $cartitems->{$productid}->{count},
                	},
	                table => 'cart',
    	            where => {cartid => $cartid, productid => $productid},
        	    );
			};
		};
	};

    $self->stash(
        page => $page,
		cartitems => $cartitems,
		discounts => $discounts,
	);

	return $self->render('cart/emptycart') unless (%{$cartitems});
	
	$self->render('cart');
};

post '/cart/' => sub{
	my $self = shift;
	my $cartid = $self->session('cartid') || undef;
	my $productid = $self->param('productid') || 0;
	my $page = {
        'url' => 'cart',
    };
    my $result = $dbi->select(
        table => 'products',
    );
    my $products = {};
    while(my $hash = $result->fetch_hash){
        $products->{$hash->{id}} = $hash;
    };
    my $cartitems = {};

    if($cartid){
        $result = $dbi->select(
            table => 'cart',
            where => {'cartid' => $cartid},
        );
        while(my $hash = $result->fetch_hash){
            $cartitems->{$hash->{productid}} = $hash;
            $cartitems->{$hash->{productid}}->{url} = $products->{$hash->{productid}}->{url};
            $cartitems->{$hash->{productid}}->{caturl} = $products->{$hash->{productid}}->{caturl};
            $cartitems->{$hash->{productid}}->{title} = $products->{$hash->{productid}}->{title};	
            $cartitems->{$hash->{productid}}->{price} = $products->{$hash->{productid}}->{price};
            $cartitems->{$hash->{productid}}->{image} = $products->{$hash->{productid}}->{image};
			$cartitems->{$hash->{productid}}->{discount} = $products->{$hash->{productid}}->{discount};
        };
    }else{
        $cartid = time;
        $self->session(cartid => $cartid);
    };

    unless($productid && $cartitems->{$productid}->{'id'}){#Defined from duplicates
		$dbi->insert(
			{
				productid => $products->{$productid}->{'id'},
                count => 1,
                cartid => $cartid,
            },
            table => 'cart',
		);
        $cartitems->{$productid} = $products->{$productid};
        $cartitems->{$productid}->{productid} = $productid;
        $cartitems->{$productid}->{count} = 1;
	};
    
	$self->stash(
    	page => $page,
        cartitems => $cartitems,
		discounts => $discounts,
    );
};

get '/catalog/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'catalog',
		'type' => 1,
	};
	my $categories = $dbi->select(
		table => 'catalog',
		column => [
			'caption',
			'url',
			'description',
		],
		where => {'storename' => $storename},
	);
	my $price = $dbi->select(
		table => 'products',
		column => [
			'caturl',
			'price',
			'url',
			'image',
		],
		where => {storename => $storename},
	);

	$self->stash(
		page => $page,
		categories => $categories->fetch_hash_all,
		price => $price->fetch_all,
	);
	$self->render('catalog');
};

get '/catalog/:caturl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $page = $dbi->select(
		table => 'catalog',
		column => [
					'title',
					'metadescription',
					'url',
					'caption',
					'description',
					'type',
				],
		where => {url => $caturl, storename => $storename},
	);

	my $result = $dbi->select(
		table => 'products',
		column => [
			'title',
			'url',
			'caturl',
			'id',
			'price',
			'image',
			'cost',
			'margin',
			'instore',
			'discount',
			'lastmod',
			'age',
		],
		where => {'caturl' => $caturl},
		append => 'order by instore desc'
	);
	
	my $has_content = $page->one;
    return $self->render(status => 404, template =>'not_found') if !$has_content;
	
	$self->stash(
		product => $result->fetch_hash_all,
		page => $has_content,
	);
	$self->render('category');
};

get '/catalog/:caturl/:produrl.html' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $produrl = $self->param('produrl');
    my $category = $dbi->select(
		table => 'catalog',
        column => [
			'caption',
			'url',
			'metadescription',
			'type',
		],
        where => {url => $caturl, storename => $storename},
	);
	my $result=$dbi->select(
		table => 'products',
		where => {
			url => $produrl,
			storename => $storename,
		},
	);
	my $has_content = $result->fetch_hash;

    return $self->render(status => 404, template => 'not_found') if !$has_content;	

	return $self->redirect_to("/catalog/$has_content->{caturl}/$produrl.html") if ($caturl ne $has_content->{caturl});

	$self->stash(
		product => $has_content,
		page => $category->one,
	);
	$self->render('product');
};

get '/about' => sub{
    my $self = shift;
    my $page = {'url' => 'about'};
    my $pages = $dbi->select(
        table => 'pages',
        column => [
            'caption',
            'url',
            'description',
			'type',
        ],
        where => {'type' => 1},
    );

    $self->stash(
		page => $page,
        pages => $pages->fetch_hash_all,
    );
};

get '/about/:pageurl' => sub{
	my $self = shift;
	my $result = $dbi->select(
		table => 'pages',
		column => [
			'title',
			'caption',
			'url',
			'metadescription',
			'description',
			'content',
		],
		where => {'url' => $self->param('pageurl')}
	);
	my $has_content = $result->fetch_hash;

    return $self->render(status => 404, template => 'not_found') if !$has_content;

	$self->stash(page => $has_content); 
	$self->render('page');
};

get '/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'index',
	};
	my $result = $dbi->select(
		table => 'products',
		column => ['cart.productid'],
		where => {storename => $storename},
		join => [
			'left outer join cart on products.id = cart.productid',
		],
		append => 'group by productid order by count(productid) desc limit 6'
	);
	$result = $result->values;

	$self->stash(r => $dbi->last_sql);

	my $products = $dbi->select(
        table => 'products',
		where => {id => $result},
    );

	$self->stash(
		page => $page,
		products => $products->fetch_hash_all,
	);
	$self->render('index');
};

get '/sitemap' => sub{
	my $self = shift;
	my $pages = $dbi->select(
		table => 'pages',
        column => [
			'url',
			'type',
			'priority',
			'changefreq',
			'lastmod',
		],
	);

	my $category = $dbi->select(
    	table => 'catalog',
        column => [
            'url',
            'type',
            'priority',
            'changefreq',
            'lastmod',
        ],
		where => {storename => $storename},
    );

	my $products = $dbi->select(
		table => 'products',
		column => [
			'url',
			'caturl',
			'lastmod',
		],
		where => {storename => $storename},
	);

	$self->stash(
		pages => $pages->fetch_hash_all,
		category => $category->fetch_hash_all,
		products => $products->fetch_hash_all,
		storename => $storename,
	);
	$self->render('sitemap');
};

app->secret($secret);
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://www.nastartshop.ru/}));
			}
		);
app->start;
