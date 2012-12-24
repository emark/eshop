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
our $dbi = DBIx::Custom->connect(
			dsn => $appconf[0],
			user => $appconf[1],
			password => $appconf[2],
			option => {mysql_enable_utf8=>1}
);

$dbi->do('SET NAMES utf8');

get '/news/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'news'
	};
	my $ua = Mojo::UserAgent->new();
	my $news = $ua->get('http://blog.nastartshop.ru/category/news/?json=1')->res->json;
    $self->stash(
		page => $page,
        news => $news);
};

get '/news/:id/' => sub{
	my $self = shift;
	my $post_id = $self->param('id') || undef;
	my $page = {
		'url' => 'news',
	};
	my $ua = Mojo::UserAgent->new();
	my $url = "http://blog.nastartshop.ru/api/get_post/?id=$post_id" if $post_id;
	my $news = $ua->get($url)->res->json;

	return $self->render(status => 404, template => 'not_found') if $news->{'status'} eq 'error';

    $self->stash(
		page => $page,
        news => $news);
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
	$self->render('checkout');
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
		$result = $dbi->select(
            table => 'cart',
            where => {'cartid' => $cartid},
        );
        while(my $hash = $result->fetch_hash){
            $cartitems = $hash;
            $cartitems->{title} = $products->{$hash->{productid}}->{title};
            $cartitems->{price} = $products->{$hash->{productid}}->{price};
            $cartitems->{id} = '';

			$dbi->insert(
				$cartitems,
				table => 'items',
			);
        };

		$self->session('cartid' => 0);

		return $self->redirect_to('/cart/thankyou/');
	}else{
		$self->stash(missing => 1);
	};
	$self->render('checkout');
};

get '/cart/thankyou/' => sub{
	my $self = shift;
	my $page = {
		url => 'thankyou',
	};
	$self->stash(page => $page);
	$self->render('thankyou');
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
		};
	}else{
		return $self->render('static/emptycart');
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
	);

	return $self->render('static/emptycart') unless (%{$cartitems});
	
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
    );
};

get '/catalog/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'catalog',
		'type' => 1,
	};
	my $categories = $dbi->select(
		table => 'pages',
		column => [
			'title',
			'url',
			'description',
		],
		where => {'type' => 0},
	);
	my $price = $dbi->select(
		table => 'products',
		column => [
			'caturl',
			'price',
			'url',
			'image',
		],
		where => 'instore >= 0',
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
						table => 'pages',
						column => [
							'title',
							'metadescription',
							'url',
							'description',
							'type',
						],
						where => {'url' => $caturl},
					);
	my $result = $dbi->select(
		table => 'products',
		column => [
			'title',
			'url',
			'id',
			'price',
			'image',
			'cost',
			'margin',
			'instore',
			'discount',
			'lastmod',
		],
		where => {'caturl' => $caturl},
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
		table => 'pages',
        column => [
			'title',
			'url',
			'metadescription',
			'type',
		],
        where => {'url' => $caturl},
	);
	my $result=$dbi->select(
		table => 'products',
        column => [
			'id',
			'title',
			'metadescription',
			'cost',
			'margin',
			'discount',
			'price',
			'description',
			'settings',
			'features',
			'image',
			'instore',
			'url',
			'photo',
			'video',
			'instruction',
			'lastmod',
		],
		where => {
			'url' => $produrl,
			'caturl' => $caturl,
		},
	);
	my $has_content = $result->fetch_hash;

    return $self->render(status => 404, template => 'not_found') if !$has_content;

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
            'title',
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
	my $products = $dbi->select(
        table => 'products',
        column => [
            'title',
            'url',
            'id',
			'cost',
			'margin',
			'discount',
            'price',
            'image',
			'caturl',
			'lastmod',
        ],
		where => {'latest' => 1},
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
	my $products = $dbi->select(
		table => 'products',
		column => [
			'url',
			'caturl',
			'lastmod',
		],
	);
	$self->stash(
		pages => $pages->fetch_hash_all,
		products => $products->fetch_hash_all,
	);
	$self->render('sitemap');
};

app->secret('ReginaSpector');
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://www.nastartshop.ru/}));
			}
		);
app->start;
